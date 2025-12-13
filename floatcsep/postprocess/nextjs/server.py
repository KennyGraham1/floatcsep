"""Python server launcher for Next.js dashboard."""

import json
import logging
import os
import platform
import re
import shutil
import socket
import stat
import subprocess
import tarfile
import threading
import time
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional
from urllib import request

from ..panel.manifest import build_manifest

logger = logging.getLogger(__name__)
MIN_NODE_VERSION = (18, 17, 0)
BUNDLED_NODE_VERSION = "20.11.1"


@dataclass
class NodeRuntime:
    """Represents a runnable Node.js installation."""

    node_path: Path
    npm_path: Path
    bin_dir: Path
    source: str

    def apply_to_env(self, env: dict) -> dict:
        """Return a copy of the environment with this runtime prepended to PATH."""

        current_path = env.get("PATH", "")
        updated = env.copy()
        updated["PATH"] = (
            f"{self.bin_dir}{os.pathsep}{current_path}" if current_path else str(self.bin_dir)
        )
        return updated


def parse_node_version(raw: str) -> Optional[tuple[int, int, int]]:
    match = re.match(r"v?(\d+)\.(\d+)\.(\d+)", raw.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def get_system_node_runtime() -> Optional[NodeRuntime]:
    node_cmd = shutil.which("node")
    npm_cmd = shutil.which("npm")
    if not node_cmd or not npm_cmd:
        return None
    try:
        result = subprocess.run(
            [node_cmd, "--version"], capture_output=True, text=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    version = parse_node_version(result.stdout)
    if not version or version < MIN_NODE_VERSION:
        return None
    return NodeRuntime(
        node_path=Path(node_cmd),
        npm_path=Path(npm_cmd),
        bin_dir=Path(node_cmd).parent,
        source="system",
    )


def _node_dist_name() -> tuple[str, str]:
    system = platform.system().lower()
    machine = platform.machine().lower()
    if system == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux-x64", ".tar.xz"
        if machine in ("aarch64", "arm64"):
            return "linux-arm64", ".tar.xz"
    elif system == "darwin":
        if machine == "arm64":
            return "darwin-arm64", ".tar.xz"
        if machine in ("x86_64", "amd64"):
            return "darwin-x64", ".tar.xz"
    elif system == "windows":
        if machine in ("x86_64", "amd64"):
            return "win-x64", ".zip"
    raise RuntimeError(
        f"Unsupported platform '{platform.system()} {platform.machine()}'. "
        "Please install Node.js 20+ manually."
    )


def _download_node_archive(target: Path, url: str) -> None:
    logger.info("Downloading Node.js runtime from %s", url)
    target.parent.mkdir(parents=True, exist_ok=True)
    with request.urlopen(url) as response, open(target, "wb") as handle:
        shutil.copyfileobj(response, handle)


def _extract_node_archive(archive: Path, destination: Path) -> Path:
    logger.info("Extracting Node.js runtime to %s", destination)
    destination.mkdir(parents=True, exist_ok=True)
    if archive.suffix == ".zip":
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(destination)
    else:
        # Handles .tar.xz
        with tarfile.open(archive, mode="r:*") as tf:
            tf.extractall(destination)
    # Find the extracted directory (node-vXX-<platform>)
    for child in destination.iterdir():
        if child.is_dir() and child.name.startswith(f"node-v{BUNDLED_NODE_VERSION}"):
            return child
    raise RuntimeError("Failed to locate extracted Node.js runtime")


def ensure_bundled_node(nextjs_dir: Path) -> NodeRuntime:
    platform_tag, archive_ext = _node_dist_name()
    cache_dir = nextjs_dir / ".cache" / "node-runtime"
    extract_root = cache_dir / f"node-v{BUNDLED_NODE_VERSION}-{platform_tag}"
    if extract_root.exists():
        logger.info("Using cached Node.js runtime at %s", extract_root)
    else:
        archive_name = f"node-v{BUNDLED_NODE_VERSION}-{platform_tag}{archive_ext}"
        download_url = f"https://nodejs.org/dist/v{BUNDLED_NODE_VERSION}/{archive_name}"
        archive_path = cache_dir / archive_name
        _download_node_archive(archive_path, download_url)
        extracted = _extract_node_archive(archive_path, cache_dir)
        extracted.rename(extract_root)
        archive_path.unlink(missing_ok=True)

    if platform.system().lower() == "windows":
        node_path = extract_root / "node.exe"
        npm_path = extract_root / "npm.cmd"
        bin_dir = extract_root
    else:
        bin_dir = extract_root / "bin"
        node_path = bin_dir / "node"
        npm_path = bin_dir / "npm"
    for path in (node_path, npm_path):
        if not path.exists():
            raise RuntimeError(f"Bundled Node.js binary missing: {path}")
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return NodeRuntime(node_path=node_path, npm_path=npm_path, bin_dir=bin_dir, source="bundled")


def ensure_node_runtime(nextjs_dir: Path) -> NodeRuntime:
    runtime = get_system_node_runtime()
    if runtime:
        logger.info("Detected Node.js %s from system PATH", runtime.node_path)
        return runtime
    logger.warning(
        "Node.js %s or newer not found. Downloading a scoped runtime (v%s).",
        ".".join(str(part) for part in MIN_NODE_VERSION),
        BUNDLED_NODE_VERSION,
    )
    return ensure_bundled_node(nextjs_dir)


def find_free_port() -> int:
    """Find an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


def ensure_nextjs_dependencies(nextjs_dir: Path, npm_cmd: List[str], env: dict) -> None:
    """Install Node dependencies if needed."""
    node_modules = nextjs_dir / "node_modules"
    if node_modules.exists():
        return
    logger.info("Installing Next.js dependencies (this may take a few minutes)...")
    try:
        subprocess.run(
            npm_cmd + ["install"],
            cwd=nextjs_dir,
            check=True,
            env=env,
        )
    except subprocess.CalledProcessError as exc:
        logger.error("Failed to install dependencies: %s", exc)
        raise RuntimeError(
            "Could not install Next.js dependencies automatically. "
            "Please ensure network access is available or install them manually."
        )


def serialize_value(value: Any) -> Any:
    """Recursively convert values to JSON-serializable types."""
    if isinstance(value, Path):
        return str(value)
    elif isinstance(value, dict):
        return {k: serialize_value(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [serialize_value(v) for v in value]
    elif hasattr(value, '__dict__'):
        # Handle dataclass or object with attributes
        return serialize_value(vars(value))
    else:
        return value


def serialize_manifest(manifest: Any) -> dict:
    """Convert Manifest dataclass to JSON-serializable dict."""
    manifest_dict = {
        "name": manifest.name,
        "start_date": manifest.start_date,
        "end_date": manifest.end_date,
        "authors": manifest.authors,
        "doi": manifest.doi,
        "journal": manifest.journal,
        "manuscript_doi": manifest.manuscript_doi,
        "exp_time": manifest.exp_time,
        "floatcsep_version": manifest.floatcsep_version,
        "pycsep_version": manifest.pycsep_version,
        "last_run": manifest.last_run,
        "catalog_doi": manifest.catalog_doi,
        "license": manifest.license,
        "date_range": manifest.date_range,
        "magnitudes": manifest.magnitudes,
        "region": {
            "name": getattr(manifest.region, "name", None),
            "bbox": list(manifest.region.get_bbox()) if manifest.region and hasattr(manifest.region, 'get_bbox') else None,
            "dh": float(manifest.region.dh) if manifest.region and hasattr(manifest.region, 'dh') else None,
        } if manifest.region else None,
        "models": serialize_value(manifest.models),
        "tests": serialize_value(manifest.tests),
        "time_windows": manifest.time_windows,
        "catalog": serialize_value(manifest.catalog),
        "results_main": {f"{tw}|{test}": serialize_value(path) for (tw, test), path in manifest.results_main.items()},
        "results_model": {f"{tw}|{test}|{model}": serialize_value(path) for (tw, test, model), path in manifest.results_model.items()},
        "app_root": str(manifest.app_root) if manifest.app_root else None,
        "exp_class": manifest.exp_class,
        "n_intervals": manifest.n_intervals,
        "horizon": manifest.horizon,
        "offset": manifest.offset,
        "growth": manifest.growth,
        "mag_min": manifest.mag_min,
        "mag_max": manifest.mag_max,
        "mag_bin": manifest.mag_bin,
        "depth_min": manifest.depth_min,
        "depth_max": manifest.depth_max,
        "run_mode": manifest.run_mode,
        "run_dir": serialize_value(manifest.run_dir),
        "config_file": serialize_value(manifest.config_file),
        "model_config": serialize_value(manifest.model_config),
        "test_config": serialize_value(manifest.test_config),
    }
    return manifest_dict


def wait_for_server(address: str, port: int, timeout: int = 60) -> bool:
    """
    Wait for the server to be ready by checking if HTTP requests succeed.

    This function first waits for the port to be open, then waits for
    the server to respond with a successful HTTP status.

    Args:
        address: Host address
        port: Port number
        timeout: Maximum time to wait in seconds

    Returns:
        True if server is ready, False if timeout
    """
    import urllib.request
    import urllib.error

    start_time = time.time()
    url = f"http://{address}:{port}/api/manifest"

    # First wait for port to be open
    logger.info("Waiting for port to be open...")
    while time.time() - start_time < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(1)
                result = sock.connect_ex((address, port))
                if result == 0:
                    logger.info("Port is open, waiting for server to be fully ready...")
                    break
        except (socket.error, OSError):
            pass
        time.sleep(0.5)
    else:
        logger.warning("Port did not open in time")
        return False

    # Now wait for HTTP to respond successfully
    while time.time() - start_time < timeout:
        try:
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    logger.info("Server is fully ready!")
                    return True
        except urllib.error.HTTPError as e:
            # Server responded but with an error - might still be compiling
            logger.debug(f"HTTP error {e.code}, waiting...")
        except (urllib.error.URLError, socket.error, OSError) as e:
            # Connection error - server not ready yet
            logger.debug(f"Connection error: {e}, waiting...")
        except Exception as e:
            logger.debug(f"Unexpected error: {e}, waiting...")
        time.sleep(1)

    logger.warning("Server did not become fully ready in time")
    return False


def run_nextjs_app(
    experiment: Any,
    port: int = 0,
    address: str = "localhost",
    show: bool = True,
    title: Optional[str] = None,
    mode: str = "dev",
) -> None:
    """
    Launch the Next.js dashboard for the experiment.

    Args:
        experiment: Experiment instance
        port: Port number (0 = auto-select)
        address: Host address
        show: Open browser automatically
        title: Window title (unused in Next.js)
        mode: 'dev' or 'start' (production)
    """
    # Build manifest
    logger.info("Building experiment manifest...")
    manifest = build_manifest(experiment)

    # Get Next.js app directory
    nextjs_dir = Path(__file__).resolve().parent

    runtime = ensure_node_runtime(nextjs_dir)
    base_env = runtime.apply_to_env(os.environ)
    # Ensure dependencies installed using the detected runtime
    ensure_nextjs_dependencies(
        nextjs_dir,
        npm_cmd=[str(runtime.npm_path)],
        env=base_env,
    )

    # Select port
    if port == 0:
        port = find_free_port()

    # Write manifest to cache for API access
    manifest_path = nextjs_dir / ".cache" / "manifest.json"
    manifest_path.parent.mkdir(exist_ok=True)

    logger.info(f"Writing manifest to {manifest_path}...")
    try:
        with open(manifest_path, "w") as f:
            manifest_dict = serialize_manifest(manifest)
            json.dump(manifest_dict, f, indent=2)
        logger.info(f"Manifest written successfully ({manifest_path.stat().st_size} bytes)")
    except Exception as e:
        logger.error(f"Failed to write manifest: {e}")
        raise

    # Environment for the Next.js process
    env = base_env.copy()
    env["MANIFEST_PATH"] = str(manifest_path.absolute())
    env["APP_ROOT"] = manifest.app_root
    env["HOSTNAME"] = address
    env["PORT"] = str(port)

    # Construct command
    cmd = [str(runtime.npm_path), "run", mode]

    logger.info(f"Starting Next.js dashboard at http://{address}:{port}")
    logger.info(f"Mode: {mode}")
    logger.debug(f"MANIFEST_PATH: {env['MANIFEST_PATH']}")
    logger.debug(f"APP_ROOT: {env['APP_ROOT']}")

    # Start the Next.js server as a subprocess
    try:
        # Start process without capturing output - let it inherit parent's stdout/stderr
        # This prevents buffering issues and allows real-time output
        process = subprocess.Popen(
            cmd,
            cwd=nextjs_dir,
            env=env,
        )

        # Open browser after server is ready
        if show:
            def open_browser_when_ready():
                logger.info("Waiting for server to be ready...")
                if wait_for_server(address, port, timeout=30):
                    logger.info(f"Opening browser at http://{address}:{port}")
                    webbrowser.open(f"http://{address}:{port}")
                else:
                    logger.warning("Server did not become ready in time. Browser not opened automatically.")

            threading.Thread(target=open_browser_when_ready, daemon=True).start()

        # Wait for the process to complete
        try:
            return_code = process.wait()
            if return_code != 0:
                logger.error(f"Next.js server exited with code {return_code}")
                raise subprocess.CalledProcessError(return_code, cmd)
        except KeyboardInterrupt:
            logger.info("\nShutting down Next.js server...")
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                logger.warning("Server did not terminate gracefully, forcing shutdown...")
                process.kill()
                process.wait()
            logger.info("Server stopped.")

    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        raise
    except Exception as e:
        logger.error(f"Failed to start Next.js server: {e}")
        raise
