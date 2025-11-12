import configparser
import hashlib
import json
import logging
import os
import platform
import shutil
import subprocess
import sys
import venv
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, List
import re
import docker
import yaml
from docker.errors import ImageNotFound, APIError


log = logging.getLogger("floatLogger")


class EnvironmentManager(ABC):
    """
    Abstract base class for managing different types of environments. This class defines the
    interface for creating, checking existence, running commands, and installing dependencies in
    various environment types.
    """

    @abstractmethod
    def __init__(self, base_name: str, model_directory: str):
        """
        Initializes the environment manager with a base name and model directory.

        Args:
            base_name (str): The base name for the environment.
            model_directory (str): The directory containing the model files.
        """
        self.base_name = base_name
        self.model_directory = model_directory

    @abstractmethod
    def create_environment(self, force=False):
        """
        Creates the environment. If 'force' is True, it will remove any existing environment
        with the same name before creating a new one.

        Args:
            force (bool): Whether to forcefully remove an existing environment and create it
             again
        """
        pass

    @abstractmethod
    def env_exists(self):
        """
        Checks if the environment already exists.

        Returns:
            bool: True if the environment exists, False otherwise.
        """
        pass

    @abstractmethod
    def run_command(self, command, **kwargs):
        """
        Executes a command within the context of the environment.

        Args:
            command (str): The command to be executed.
        """
        pass

    @abstractmethod
    def install_dependencies(self):
        """
        Installs the necessary dependencies for the environment based on the specified
        configuration or requirements.
        """
        pass

    def generate_env_name(self) -> str:
        """
        Generates a unique environment name by hashing the model directory and appending it
        to the base name.

        Returns:
            str: A unique name for the environment.
        """
        dir_hash = hashlib.md5(self.model_directory.encode()).hexdigest()[:8]
        return f"{self.base_name}_{dir_hash}"


class CondaManager(EnvironmentManager):
    """
    Manages a conda (or mamba) environment, providing methods to create, check and manipulate
    conda environments specifically.
    """

    def __init__(self, base_name: str, model_directory: str):
        """
        Initializes the Conda environment manager with the specified base name and model
        directory. It also generates the environment name and detects the package manager (conda
        or mamba) to install dependencies.

        Args:
            base_name (str): The base name, i.e., model name, for the conda environment.
            model_directory (str): The directory containing the model files.
        """
        self.base_name = base_name.replace(" ", "_")
        self.model_directory = model_directory
        self.env_name = self.generate_env_name()
        self.package_manager = self.detect_package_manager()

    @staticmethod
    def detect_package_manager():
        """
        Detects whether 'mamba' or 'conda' is available as the package manager.

        Returns:
            str: The name of the detected package manager ('mamba' or 'conda').
        """
        if shutil.which("mamba"):
            log.info("Mamba detected, using mamba as package manager.")
            return "mamba"
        log.info("Mamba not detected, using conda as package manager.")
        return "conda"

    @staticmethod
    def _conda_exe() -> str:
        exe = shutil.which("conda")
        if not exe:
            raise RuntimeError("conda not found on PATH")
        return exe

    def _build_exe(self) -> str:
        # Use mamba if available, otherwise conda
        return shutil.which("mamba") or self._conda_exe()

    def detect_python_version(self) -> str:
        """
        Determines the required Python version from setup files in the model directory. It
        checks 'setup.py', 'pyproject.toml', and 'setup.cfg' (in that order), for version
        specifications.

        Returns:
            version (str): The build python version.
        """

        def read_python_requires() -> Union[str, None]:
            # setup.cfg
            cfg = os.path.join(self.model_directory, "setup.cfg")
            if os.path.exists(cfg):
                cp = configparser.ConfigParser()
                cp.read(cfg)
                req = cp.get("options", "python_requires", fallback="").strip()
                if req:
                    return req

            # pyproject.toml
            ppt = os.path.join(self.model_directory, "pyproject.toml")
            if os.path.exists(ppt):
                try:
                    import tomllib  # py3.11+

                    with open(ppt, "rb") as f:
                        data = tomllib.load(f)
                    req = (data.get("project", {}) or {}).get("requires-python")
                    if req:
                        return str(req).strip()
                except Exception:
                    pass

            # setup.py
            spy = os.path.join(self.model_directory, "setup.py")
            if os.path.exists(spy):
                with open(spy, "r", encoding="utf-8") as f:
                    txt = f.read()
                m = re.search(r"python_requires\s*=\s*['\"]([^'\"]+)['\"]", txt)
                if m:
                    return m.group(1).strip()
            return None

        def mm_from_str(v: str) -> Union[tuple[int, int], None]:
            m = re.search(r"(\d+)\.(\d+)", v)
            return (int(m.group(1)), int(m.group(2))) if m else None

        req = read_python_requires()
        if not req:
            return f"{sys.version_info.major}.{sys.version_info.minor}"

        spec = req.replace(" ", "").replace("==", "=")
        parts = spec.split(",")

        upper_ver, upper_inclusive = None, False
        for p in parts:
            if p.startswith("<=") or p.startswith("<"):
                v = mm_from_str(p)
                if v:
                    if (upper_ver is None) or (v < upper_ver):
                        upper_ver = v
                        upper_inclusive = p.startswith("<=")
        if upper_ver:
            maj, minor = upper_ver
            if not upper_inclusive:
                minor = max(0, minor - 1)
            return f"{maj}.{minor}"

        for p in parts:
            if p.startswith("="):
                v = mm_from_str(p)
                if v:
                    maj, minor = v
                    return f"{maj}.{minor}"

        for p in parts:
            if p.startswith(">=") or p.startswith(">"):
                v = mm_from_str(p)
                if v:
                    maj, minor = v
                    return f"{maj}.{minor}"

        v = mm_from_str(spec)
        if v:
            maj, minor = v
            return f"{maj}.{minor}"

        return f"{sys.version_info.major}.{sys.version_info.minor}"

    def create_environment(self, force=False):
        """
        Creates a conda environment using either an environment.yml file or the specified
        Python version in setup.py/setup.cfg or project/toml. If 'force' is True, any existing
        environment with the same name will be removed first.

        Args:
            force (bool): Whether to forcefully remove an existing environment.
        """
        build = self._build_exe()

        if force and self.env_exists():
            log.info(f"Removing existing env: {self.env_name}")
            subprocess.run([build, "env", "remove", "-n", self.env_name, "-y", "-q"])

        if self.env_exists():
            return

        env_file = os.path.join(self.model_directory, "environment.yml")
        py_spec = self.detect_python_version()
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            deps = data.get("dependencies") or []

            has_python_key = any(
                isinstance(d, str) and d.strip().startswith("python") for d in deps
            )

            if has_python_key:
                log.info(f"Creating env {self.env_name} from environment.yml")
                p = subprocess.Popen(
                    [build, "env", "create", "-n", self.env_name, "-f", env_file, "-y"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
            else:
                log.info(f"Creating env {self.env_name} with python={py_spec}")
                subprocess.run(
                    [build, "create", "-n", self.env_name, "-y", "-q", f"python={py_spec}"],
                )

                log.info(f"Updating env {self.env_name} from environment.yml")
                p = subprocess.Popen(
                    [build, "env", "update", "-n", self.env_name, "-f", env_file, "-y"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    universal_newlines=True,
                )
        else:
            log.info(f"Creating env {self.env_name} with python={py_spec}")
            p = subprocess.Popen(
                [build, "create", "-n", self.env_name, "-y", f"python={py_spec}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            )
        assert p.stdout is not None
        for line in p.stdout:
            log.debug(f"[{build.split('/')[-1]}] {line.rstrip()}")
        p.wait()

        if not self.env_exists():
            raise RuntimeError(f"Env {self.env_name} was not created successfully")

        self.install_dependencies()

    def env_exists(self) -> bool:
        """
        Checks if the conda environment exists by querying the list of existing conda
        environments.

        Returns:
            bool: True if the conda environment exists, False otherwise.
        """
        conda = self._conda_exe()
        res = subprocess.run(
            [conda, "env", "list", "--json"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True,
        )
        envs = json.loads(res.stdout).get("envs", [])
        return any(p.endswith(os.path.sep + self.env_name) for p in envs)

    def install_dependencies(self) -> None:

        conda = self._conda_exe()
        conda_base = [conda, "run", "--live-stream", "-n", self.env_name]
        abs_model = os.path.abspath(self.model_directory)
        log.info(f"Installing pip dependencies in env: {self.env_name}")

        cmd = conda_base + ["python", "-m", "pip", "install", "-e", abs_model]

        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, text=True
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.debug(f"[pip] {line.rstrip()}")
        rc = process.wait()
        if rc != 0:
            raise RuntimeError(
                f"[{self.base_name}] pip install failed with exit code {rc}: {cmd}"
            )

    def run_command(self, command, **kwargs) -> None:
        """
        Runs a specified command within the conda environment.

        Args:
            command (str): The command to be executed in the conda environment.
        """
        conda = self._conda_exe()
        cmd = [conda, "run", "--live-stream", "-n", self.env_name, command]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.debug(f"[{self.base_name}] {line.rstrip()}")
        rc = process.wait()

        if rc != 0:
            log.error(f"[{self.base_name}] Command exited with code {rc}: {command}")
        else:
            log.debug(f"[{self.base_name}] Command finished successfully.")


class VenvManager(EnvironmentManager):
    """
    Manages a virtual environment created using Python's venv module. Provides methods to
    create, check, and manipulate virtual environments.
    """

    def __init__(self, base_name: str, model_directory: str) -> None:
        """
        Initializes the virtual environment manager with the specified base name and model
        directory.

        Args:
            base_name (str): The base name (i.e., model name) for the virtual environment.
            model_directory (str): The directory containing the model files.
        """

        self.base_name = base_name.replace(" ", "_")
        self.model_directory = model_directory
        self.env_name = self.generate_env_name()
        self.env_path = os.path.join(model_directory, self.env_name)

    def create_environment(self, force=False):
        """
        Creates a virtual environment in the specified model directory. If 'force' is True,
        any existing virtual environment will be removed before creation.

        Args:
            force (bool): Whether to forcefully remove an existing virtual environment.
        """
        if force and self.env_exists():
            log.info(f"Removing existing virtual environment: {self.env_name}")
            shutil.rmtree(self.env_path)

        if not self.env_exists():
            log.info(f"Creating virtual environment: {self.env_name}")
            venv.EnvBuilder(with_pip=True, clear=True, symlinks=True).create(self.env_path)
            log.info(f"\tVirtual environment created: {self.env_name}")
            self.install_dependencies()

    def env_exists(self) -> bool:
        """
        Checks if the virtual environment exists by verifying the presence of its directory.

        Returns:
            bool: True if the virtual environment exists, False otherwise.
        """
        return os.path.isdir(self.env_path)

    def install_dependencies(self) -> None:
        """
        Installs dependencies in the virtual environment using pip, based on the model
        directory's configuration.
        """
        log.info(f"Installing dependencies in virtual environment: {self.env_name}")
        pip_executable = os.path.join(self.env_path, "bin", "pip")
        cmd = f"{pip_executable} install -e {os.path.abspath(self.model_directory)}"
        self.run_command(cmd)

    def run_command(self, command, **kwargs) -> None:
        """
        Executes a specified command in the virtual environment and logs the output.

        Args:
            command (str): The command to be executed in the virtual environment.
        """

        activate_script = os.path.join(self.env_path, "bin", "activate")

        env = os.environ.copy()
        for var in (
            "PYTHONPATH",
            "PYTHONHOME",
            "CONDA_PREFIX",
            "CONDA_DEFAULT_ENV",
            "CONDA_SHLVL",
            "__PYVENV_LAUNCHER__",
        ):
            env.pop(var, None)
        env["VIRTUAL_ENV"] = self.env_path
        env["PATH"] = os.path.join(self.env_path, "bin") + os.pathsep + env.get("PATH", "")

        full_command = f"bash -lc 'source \"{activate_script}\"' && {command}"

        process = subprocess.Popen(
            full_command,
            shell=True,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            log.info(f"[{self.base_name}]: {line.rstrip()}")

        rc = process.wait()
        if rc != 0:
            raise RuntimeError(
                f"[{self.base_name}] Command failed with exit code {rc}: {command}"
            )


class DockerManager(EnvironmentManager):
    """
    Manages a Docker environment, providing methods to create, check and manipulate Docker
    containers for the environment.
    """

    def __init__(self, base_name: str, model_directory: str) -> None:
        self.base_name = base_name.replace(" ", "_")
        self.model_directory = model_directory

        # use a lower-case slug for tags
        slug = self.base_name.lower()
        self.image_tag = f"{slug}_image"
        self.container_name = f"{slug}_container"

        # Docker SDK client
        self.client = docker.from_env()

    def create_environment(self, force: bool = False) -> None:
        """
        Build (or rebuild) the Docker image for this model.
        """

        # If forced, remove the existing image
        if force and self.env_exists():
            log.info(f"[{self.base_name}] Removing existing image '{self.image_tag}'")
            try:
                self.client.images.remove(self.image_tag, force=True)
            except APIError as e:
                log.warning(f"[{self.base_name}] Could not remove image: {e}")

        # If image is missing or rebuild was requested, build it now
        if force or not self.env_exists():
            build_path = os.path.abspath(self.model_directory)
            uid, gid = os.getuid(), os.getgid()
            build_args = {
                "USER_UID": str(uid),
                "USER_GID": str(gid),
            }
            log.info(f"[{self.base_name}] Building image '{self.image_tag}' from {build_path}")

            build_logs = self.client.api.build(
                path=build_path,
                tag=self.image_tag,
                rm=True,
                decode=True,
                buildargs=build_args,
                nocache=False,  # todo: create model arg for --no-cache
            )

            # Stream each chunk
            for chunk in build_logs:
                if "stream" in chunk:
                    for line in chunk["stream"].splitlines():
                        log.debug(f"[{self.base_name}][build] {line}")
                elif "errorDetail" in chunk:
                    msg = chunk["errorDetail"].get("message", "").strip()
                    log.error(f"[{self.base_name}][build error] {msg}")
                    raise RuntimeError(f"Docker build error: {msg}")
            log.info(f"[{self.base_name}] Successfully built '{self.image_tag}'")

    def env_exists(self) -> bool:
        """
        Checks if the Docker image with the given tag already exists.

        Returns:
            bool: True if the Docker image exists, False otherwise.
        """
        """
        Returns True if an image with our tag already exists locally.
        """
        try:
            self.client.images.get(self.image_tag)
            return True
        except ImageNotFound:
            return False

    def run_command(
        self,
        command: List[str] = None,
        run_label: str = None,
        input_volume: Union[Path, str] = None,
        forecast_volume: Union[Path, str] = None,
        mem_limit=None,
        cpus=None,
    ) -> None:
        """
        Runs the model’s Docker container with input/ and forecasts/ mounted.
        Streams logs and checks for non-zero exit codes.
        """
        model_root = Path(self.model_directory).resolve()
        host_volume_input = input_volume or model_root / "input"
        host_volume_forecasts = forecast_volume or model_root / "forecasts"
        mounts = {
            host_volume_input: {"bind": "/app/input", "mode": "rw"},
            host_volume_forecasts: {"bind": "/app/forecasts", "mode": "rw"},
        }

        uid, gid = os.getuid(), os.getgid()

        run_kwargs = {
            "image": self.image_tag,
            "remove": False,
            "volumes": mounts,
            "detach": True,
        }
        if platform.system() != "Windows":
            try:
                run_kwargs["user"] = f"{os.getuid()}:{os.getgid()}"
            except AttributeError:
                pass

        if run_label:
            run_kwargs["labels"] = {"model_timewindow": run_label}
        if mem_limit:
            run_kwargs["mem_limit"] = mem_limit
        if cpus:
            run_kwargs["nano_cpus"] = int(float(cpus) * 1e9)

        log.info(f"[{self.base_name}] Launching Docker container")

        try:
            container = self.client.containers.run(**run_kwargs)
        except docker.errors.APIError as e:
            log.error(f"[{self.base_name}] Failed to start container: {e}")
            raise RuntimeError(f"[{self.base_name}] Failed to start container: {e}")

        cid = container.id
        log.debug(f"[{self.base_name}] Using container {cid[:12]} for task {run_label}")
        exit_code = container.wait().get("StatusCode", 1)

        if exit_code != 0:
            logs = container.logs(stdout=True, stderr=True, tail=2000)
            log.error(
                f"[{self.base_name}] Container {cid[:12]} for task name {run_label} exited with"
                f" code {exit_code}."
            )
            log.debug(f"[{self.base_name}]. Last logs:\n{logs.decode(errors='ignore')}")
            container.remove(force=True)
            raise RuntimeError(
                f"[{self.base_name}] Container {cid[:12]} for task name {run_label} exited with"
                f" code {exit_code}."
            )
        else:
            container.remove(force=True)
            log.info(f"[{self.base_name}] Finished successfully.")

    def install_dependencies(self) -> None:
        """
        Installs dependencies for Docker-based models. This is typically handled by the Dockerfile,
        so no additional action is needed here.
        """
        log.info("No additional dependency installation required for Docker environments.")

    @staticmethod
    def kill_containers(label_key: str, label_value_prefix: str = None):
        client = docker.from_env()
        filters = (
            {"label": label_key}
            if label_value_prefix is None
            else {"label": f"{label_key}={label_value_prefix}"}
        )

        containers = client.containers.list(all=True, filters=filters)
        for c in containers:
            labels = c.labels or {}
            if label_value_prefix and not (
                labels.get(label_key, "").startswith(label_value_prefix)
            ):
                continue
            try:
                c.kill()
            except Exception:
                pass
            try:
                c.remove(force=True)
            except Exception:
                pass
            log.warning(f"[Engine] killed {c.id[:12]} labels={labels}")


class EnvironmentFactory:
    """Factory class for creating instances of environment managers based on the specified
    type."""

    @staticmethod
    def get_env(
        build: str = None, model_name: str = "model", model_path: str = None
    ) -> EnvironmentManager:
        """
        Returns an instance of an environment manager based on the specified build type. It
        checks the current environment type and can return a conda, venv, or Docker environment
        manager.

        Args:
            build (str): The desired type of environment ('conda', 'venv', or 'docker').
            model_name (str): The name of the model for which the environment is being created.
            model_path (str): The path to the model directory.

        Returns:
            EnvironmentManager: An instance of the appropriate environment manager.

        Raises:
            Exception: If an invalid environment type is specified.
        """
        run_env = EnvironmentFactory.check_environment_type()
        if run_env != build and build and build != "docker":
            log.warning(
                f"Selected build environment ({build}) for this model is different than that of"
                f" the experiment run. Consider selecting the same environment."
            )
        if build in ["conda", "micromamba"] or (
            not build and run_env in ["conda", "micromamba"]
        ):
            return CondaManager(
                base_name=f"{model_name}",
                model_directory=os.path.abspath(model_path),
            )
        elif build == "venv" or (not build and run_env == "venv"):
            return VenvManager(
                base_name=f"{model_name}",
                model_directory=os.path.abspath(model_path),
            )
        elif build == "docker":
            return DockerManager(
                base_name=f"{model_name}",
                model_directory=os.path.abspath(model_path),
            )
        else:
            raise Exception(
                "Wrong environment selection. Please choose between "
                '"conda", "venv" or "docker".'
            )

    @staticmethod
    def check_environment_type() -> Union[str, None]:
        if "VIRTUAL_ENV" in os.environ:
            log.info("Detected virtual environment.")
            return "venv"
        try:
            result = subprocess.run(
                ["conda", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode == 0:
                log.info("Detected conda environment.")
                return "conda"
            else:
                log.warning(
                    "Conda command failed with return code: {}".format(result.returncode)
                )
        except FileNotFoundError:
            log.warning("Conda not found in PATH.")

        try:
            result = subprocess.run(
                ["micromamba", "info"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if result.returncode == 0:
                log.info("Detected micromamba environment.")
                return "micromamba"
            else:
                log.warning(
                    "Micromamba command failed with return code: {}".format(result.returncode)
                )
        except FileNotFoundError:
            log.warning("Micromamba not found in PATH.")

        return None
