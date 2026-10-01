"""Python server launcher for Next.js dashboard."""

import json
import logging
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional

from ..panel.manifest import build_manifest
from .runtime import NodeRuntime, ensure_node_runtime, ensure_nextjs_dependencies
from .schemas import ManifestModel, external_models, finite_json

logger = logging.getLogger(__name__)

# Production builds get their own output directory, so running `next dev` (which
# writes to `.next`) never mixes its artifacts into a production build.
PROD_DIST_DIR = ".next-prod"

# Files and directories whose changes require a new production build.
BUILD_INPUTS = (
    "app",
    "components",
    "hooks",
    "lib",
    "public",
    "next.config.js",
    "package.json",
    "package-lock.json",
    "postcss.config.js",
    "tailwind.config.ts",
    "tsconfig.json",
)


def find_free_port(address: str = "localhost") -> int:
    """Find an available port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((address, 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


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
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=30) as response:
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


def _newest_input_mtime(nextjs_dir: Path) -> float:
    newest = 0.0
    for name in BUILD_INPUTS:
        path = nextjs_dir / name
        if path.is_file():
            newest = max(newest, path.stat().st_mtime)
        elif path.is_dir():
            for child in path.rglob("*"):
                if child.is_file():
                    newest = max(newest, child.stat().st_mtime)
    return newest


def _build_is_current(nextjs_dir: Path) -> bool:
    build_id = nextjs_dir / PROD_DIST_DIR / "BUILD_ID"
    return build_id.exists() and build_id.stat().st_mtime >= _newest_input_mtime(nextjs_dir)


def _build_dashboard(nextjs_dir: Path, runtime: NodeRuntime, env: dict) -> bool:
    """Create a production build. Returns False (and logs why) if it fails."""
    logger.info("Building the dashboard (only needed after installing or updating)...")
    result = subprocess.run(
        [str(runtime.npm_path), "run", "build"],
        cwd=nextjs_dir,
        env={**env, "NEXT_DIST_DIR": PROD_DIST_DIR},
    )
    if result.returncode != 0:
        logger.warning("Dashboard build failed (exit code %s).", result.returncode)
        return False
    return True


def _raise_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt


def _stop_process_tree(process: subprocess.Popen) -> None:
    """Stop npm and everything it started (npm does not forward signals reliably)."""
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(process.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        logger.warning("Server did not terminate gracefully, forcing shutdown...")
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        process.kill()
        process.wait()


def _library_versions() -> dict:
    versions = {}
    try:
        from floatcsep import __version__ as floatcsep_version

        versions["FLOATCSEP_VERSION"] = str(floatcsep_version)
    except Exception:  # pragma: no cover - version metadata is optional
        pass
    try:
        import csep

        versions["PYCSEP_VERSION"] = str(csep.__version__)
    except Exception:  # pragma: no cover
        pass
    return versions


def run_nextjs_app(
    experiment: Any,
    port: int = 0,
    address: str = "localhost",
    show: bool = True,
    title: Optional[str] = None,
    mode: str = "auto",
) -> None:
    """
    Launch the Next.js dashboard for the experiment.

    Args:
        experiment: Experiment instance
        port: Port number (0 = auto-select)
        address: Host address. The server only listens on this address.
        show: Open browser automatically
        title: Window title (unused in Next.js)
        mode: 'auto' (production build, rebuilt when the dashboard sources change,
            falling back to 'dev' if the build fails), 'start' (production) or
            'dev' (development server with hot reload)
    """
    # Build manifest
    logger.info("Building experiment manifest...")
    manifest = build_manifest(experiment)
    # Forecasts evaluated outside floatCSEP, mapped too (see schemas.external_models)
    declaration = experiment.registry.abs("external_forecasts.json")
    manifest.models.extend(external_models(declaration, manifest.time_windows))

    # Validate using Pydantic
    manifest_model = ManifestModel.model_validate(manifest)

    # Get Next.js app directory
    nextjs_dir = Path(__file__).resolve().parent

    runtime = ensure_node_runtime(nextjs_dir)
    base_env = runtime.apply_to_env(os.environ)
    base_env["NEXT_TELEMETRY_DISABLED"] = "1"
    # Ensure dependencies installed using the detected runtime
    ensure_nextjs_dependencies(
        nextjs_dir,
        npm_cmd=[str(runtime.npm_path)],
        env=base_env,
    )

    # Select port
    if port == 0:
        port = find_free_port(address)

    # Write manifest to cache for API access
    cache_dir = nextjs_dir / ".cache"
    manifest_path = cache_dir / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Writing manifest to {manifest_path}...")
    try:
        with open(manifest_path, "w") as f:
            # Serialize using Pydantic
            json.dump(
                finite_json(manifest_model.model_dump(mode="json", by_alias=True)),
                f,
                allow_nan=False,
            )
        logger.info(
            f"Manifest written successfully ({manifest_path.stat().st_size} bytes)"
        )
    except Exception as e:
        logger.error(f"Failed to write manifest: {e}")
        raise

    # Environment for the Next.js process
    env = base_env.copy()
    env["MANIFEST_PATH"] = str(manifest_path.absolute())
    env["APP_ROOT"] = str(manifest.app_root)
    env["HOSTNAME"] = address
    env["PORT"] = str(port)
    # The API routes parse catalogs and forecasts with this interpreter, which is
    # the one floatCSEP runs in (a bare `python` on PATH may be another env).
    env["FLOATCSEP_PYTHON"] = sys.executable
    env["FLOATCSEP_DASHBOARD_CACHE"] = str(cache_dir / "data")
    env.update(_library_versions())

    mode = (mode or "auto").lower()
    if mode in ("auto", "start"):
        if _build_is_current(nextjs_dir) or _build_dashboard(nextjs_dir, runtime, env):
            mode = "start"
        elif mode == "auto":
            logger.warning("Falling back to the development server.")
            mode = "dev"
        else:
            raise RuntimeError("The dashboard's production build failed (see the log above).")
    if mode == "start":
        env["NEXT_DIST_DIR"] = PROD_DIST_DIR

    # Construct command
    cmd = [str(runtime.npm_path), "run", mode, "--", "--port", str(port), "--hostname", address]

    logger.info(f"Starting Next.js dashboard at http://{address}:{port}")
    logger.info(f"Mode: {mode}")
    logger.debug(f"MANIFEST_PATH: {env['MANIFEST_PATH']}")
    logger.debug(f"APP_ROOT: {env['APP_ROOT']}")

    # Start the Next.js server in its own process group, so that stopping it
    # also stops the `next` process npm spawns (no orphaned server on the port).
    group = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    try:
        # Output is inherited (not captured) so the server logs appear in real time.
        process = subprocess.Popen(cmd, cwd=nextjs_dir, env=env, **group)
    except FileNotFoundError:
        logger.error(f"Command not found: {cmd[0]}")
        raise

    # Treat SIGTERM like Ctrl+C, so the cleanup below also runs when killed.
    previous_handler = None
    try:
        previous_handler = signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    except ValueError:  # not in the main thread
        pass

    # Open browser after server is ready
    if show:

        def open_browser_when_ready():
            logger.info("Waiting for server to be ready...")
            if wait_for_server(address, port, timeout=120):
                logger.info(f"Opening browser at http://{address}:{port}")
                webbrowser.open(f"http://{address}:{port}")
            else:
                logger.warning(
                    "Server did not become ready in time. Browser not opened automatically."
                )

        threading.Thread(target=open_browser_when_ready, daemon=True).start()

    try:
        return_code = process.wait()
        if return_code != 0:
            logger.error(f"Next.js server exited with code {return_code}")
            raise subprocess.CalledProcessError(return_code, cmd)
    except KeyboardInterrupt:
        logger.info("\nShutting down Next.js server...")
    finally:
        _stop_process_tree(process)
        if previous_handler is not None:
            signal.signal(signal.SIGTERM, previous_handler)
    logger.info("Server stopped.")
