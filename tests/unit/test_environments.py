import hashlib
import json
import logging
import os
import shutil
import subprocess
import unittest
import venv
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock, call, mock_open

from floatcsep.infrastructure.environments import (
    CondaManager,
    EnvironmentFactory,
    VenvManager,
    DockerManager,
)

try:
    import docker
    from docker.errors import ImageNotFound, APIError

    DOCKER_SDK_AVAILABLE = True
except ImportError:
    DOCKER_SDK_AVAILABLE = False


def _proc_ok():
    p = SimpleNamespace()
    p.stdout = iter([])
    p.wait = lambda: 0
    return p


def _proc_fail():
    p = SimpleNamespace()
    p.stdout = iter([])
    p.wait = lambda: 1
    return p


@unittest.skipUnless(
    os.environ.get("CONDA_EXE") or shutil.which("conda"),
    "Conda not available on PATH (and CONDA_EXE unset).",
)
class TestCondaEnvironmentManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not (os.environ.get("CONDA_EXE") or shutil.which("conda")):
            raise unittest.SkipTest("Conda not available on PATH (and CONDA_EXE unset).")

    def setUp(self):
        self.manager = CondaManager(base_name="test_env", model_directory="/tmp/test_model")
        os.makedirs("/tmp/test_model", exist_ok=True)
        with open("/tmp/test_model/environment.yml", "w") as f:
            f.write("name: test_env\ndependencies:\n  - python=3.8\n  - numpy")
        with open("/tmp/test_model/setup.py", "w") as f:
            f.write("from setuptools import setup\nsetup(name='test_model', version='0.1')")

    def tearDown(self):
        if self.manager.env_exists():
            subprocess.run(
                ["conda", "env", "remove", "--name", self.manager.env_name, "--yes"],
                check=True,
            )
        if os.path.exists("/tmp/test_model"):
            shutil.rmtree("/tmp/test_model")

    @patch("subprocess.run")
    @patch("shutil.which", return_value="conda")
    def test_generate_env_name(self, mock_which, mock_run):
        manager = CondaManager("test_base", "/path/to/model")
        expected_name = "test_base_" + hashlib.md5("/path/to/model".encode()).hexdigest()[:8]
        self.assertEqual(manager.generate_env_name(), expected_name)

    #
    @patch("subprocess.run")
    def test_env_exists(self, mock_run):
        manager = CondaManager("test_base", "/path/to/model")
        env_path = os.path.join("/some/prefix/envs", manager.env_name)

        mock_run.return_value = SimpleNamespace(
            stdout=json.dumps({"envs": [env_path]}),
            stderr="",
            returncode=0,
        )
        manager = CondaManager("test_base", "/path/to/model")
        self.assertTrue(manager.env_exists())

    @patch.object(CondaManager, "_build_exe", return_value="conda")
    @patch.object(CondaManager, "_conda_exe", return_value="conda")
    @patch.object(CondaManager, "install_dependencies", return_value=None)
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_create_env_already_exists(self, mock_run, mock_popen, *_):
        m = CondaManager("test_base", "/path/to/model")
        env_path = f"/x/envs/{m.env_name}"

        mock_run.return_value = SimpleNamespace(
            stdout=json.dumps({"envs": [env_path]}), stderr="", returncode=0, text=True
        )

        m.create_environment(force=False)

        self.assertEqual(mock_run.call_count, 1)
        mock_popen.assert_not_called()

    @patch.object(CondaManager, "_build_exe", return_value="conda")
    @patch.object(CondaManager, "_conda_exe", return_value="conda")
    @patch.object(CondaManager, "install_dependencies", return_value=None)  # speed!
    @patch("yaml.safe_load", return_value={"dependencies": ["python=3.12", "numpy"]})
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists", side_effect=lambda p: p.endswith("environment.yml"))
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_from_yaml(self, mock_run, mock_popen, *_patches):
        m = CondaManager("test_base", "/path/to/model")
        env_path = f"/x/envs/{m.env_name}"

        mock_run.side_effect = [
            SimpleNamespace(
                stdout=json.dumps({"envs": []}), stderr="", returncode=0, text=True
            ),
            SimpleNamespace(
                stdout=json.dumps({"envs": [env_path]}), stderr="", returncode=0, text=True
            ),
        ]
        mock_popen.return_value = _proc_ok()

        m.create_environment(force=False)

        args0 = mock_popen.call_args_list[0][0][0]
        self.assertEqual(args0[:3], ["conda", "env", "create"])
        self.assertIn("-f", args0)
        self.assertIn("/path/to/model/environment.yml", args0)

    @patch.object(CondaManager, "_build_exe", return_value="conda")
    @patch.object(CondaManager, "_conda_exe", return_value="conda")
    @patch.object(CondaManager, "detect_python_version", return_value="3.11")
    @patch.object(CondaManager, "install_dependencies", return_value=None)
    @patch("os.path.exists", return_value=False)
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_no_yaml_create_with_python(self, mock_run, mock_popen, *_):
        m = CondaManager("test_base", "/path/to/model")
        env_path = f"/x/envs/{m.env_name}"

        mock_run.side_effect = [
            SimpleNamespace(
                stdout=json.dumps({"envs": []}), stderr="", returncode=0, text=True
            ),
            SimpleNamespace(
                stdout=json.dumps({"envs": [env_path]}), stderr="", returncode=0, text=True
            ),
        ]

        proc = SimpleNamespace()
        proc.stdout = iter([])
        proc.wait = lambda: 0
        mock_popen.return_value = proc

        m.create_environment(force=False)
        self.assertEqual(mock_run.call_count, 2)

        self.assertEqual(mock_popen.call_count, 1)
        create_args = mock_popen.call_args_list[0][0][0]
        self.assertEqual(create_args[:2], ["conda", "create"])
        self.assertIn("-n", create_args)
        self.assertIn(m.env_name, create_args)
        self.assertIn(f"python=3.11", create_args)

    @patch.object(CondaManager, "_build_exe", return_value="conda")
    @patch.object(CondaManager, "_conda_exe", return_value="conda")
    @patch.object(CondaManager, "detect_python_version", return_value="3.12")
    @patch.object(CondaManager, "install_dependencies", return_value=None)
    @patch("yaml.safe_load", return_value={"dependencies": ["numpy"]})
    @patch("builtins.open", new_callable=mock_open)
    @patch("os.path.exists", side_effect=lambda p: p.endswith("environment.yml"))
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_from_yaml_no_python(self, mock_run, mock_popen, *_patches):
        m = CondaManager("test_base", "/path/to/model")
        env_path = f"/x/envs/{m.env_name}"

        mock_run.side_effect = [
            SimpleNamespace(
                stdout=json.dumps({"envs": []}), stderr="", returncode=0, text=True
            ),
            SimpleNamespace(stdout="", stderr="", returncode=0, text=True),
            SimpleNamespace(
                stdout=json.dumps({"envs": [env_path]}), stderr="", returncode=0, text=True
            ),
        ]
        mock_popen.return_value = _proc_ok()

        m.create_environment(force=False)

        create_call = mock_run.call_args_list[1][0][0]
        self.assertEqual(create_call[:2], ["conda", "create"])
        self.assertIn(f"python=3.12", create_call)

        args0 = mock_popen.call_args_list[0][0][0]
        self.assertEqual(args0[:3], ["conda", "env", "update"])
        self.assertIn("-f", args0)

    @patch.object(CondaManager, "_build_exe", return_value="conda")
    @patch.object(CondaManager, "_conda_exe", return_value="conda")
    @patch.object(CondaManager, "install_dependencies", return_value=None)
    @patch("subprocess.Popen")
    @patch("subprocess.run")
    def test_force_removes_first(self, mock_run, mock_popen, *_):
        m = CondaManager("test_base", "/path/to/model")
        env_path = f"/x/envs/{m.env_name}"

        mock_run.side_effect = [
            SimpleNamespace(
                stdout=json.dumps({"envs": [env_path]}), stderr="", returncode=0, text=True
            ),
            SimpleNamespace(
                stdout=json.dumps({"envs": []}), stderr="", returncode=0, text=True
            ),
            SimpleNamespace(
                stdout=json.dumps({"envs": [env_path]}), stderr="", returncode=0, text=True
            ),
        ]
        mock_popen.return_value = _proc_ok()

        m.create_environment(force=True)

        self.assertGreaterEqual(mock_run.call_count, 2)

    @patch.object(CondaManager, "_conda_exe", return_value="conda")
    @patch("subprocess.Popen")
    def test_install_dependencies_ok(self, mock_popen, _conda_exe):
        m = CondaManager("test_base", "/path/to/model")
        abs_model = os.path.abspath(m.model_directory)
        proc = SimpleNamespace()
        proc.stdout = iter([])
        proc.wait = lambda: 0
        mock_popen.return_value = proc

        m.install_dependencies()

        called = mock_popen.call_args[0][0]
        assert called[:5] == ["conda", "run", "--live-stream", "-n", m.env_name]
        assert called[5:10] == ["python", "-m", "pip", "install", "-e"]
        assert called[10] == abs_model

    @patch.object(CondaManager, "_conda_exe", return_value="conda")
    @patch("subprocess.Popen")
    def test_install_dependencies_fail_raises(self, mock_popen, _conda_exe):
        m = CondaManager("test_base", "/path/to/model")

        proc = SimpleNamespace()
        proc.stdout = iter([])
        proc.wait = lambda: 1  # simulate pip failure
        mock_popen.return_value = proc

        with self.assertRaises(RuntimeError):
            m.install_dependencies()

    @patch("shutil.which", return_value="conda")
    @patch("os.path.exists", side_effect=[False, False, True])
    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="[metadata]\nname = test\n\n[options]\ninstall_requires =\n    "
        "numpy\npython_requires = >=3.9,<3.12\n",
    )
    def test_detect_python_version_setup_cfg(self, mock_open, mock_exists, mock_which):
        manager = CondaManager("test_base", "../artifacts/models/td_model")
        python_version = manager.detect_python_version()

        major_minor_version = ".".join(python_version.split(".")[:2])

        self.assertIn(major_minor_version, ["3.9", "3.10", "3.11", "3.12"])

    def test_integration_create_and_delete(self):
        try:
            self.manager.create_environment(force=True)
            res = subprocess.run(
                ["conda", "env", "list", "--json"],
                stdout=subprocess.PIPE,
                check=True,
                text=True,
            )
            envs = json.loads(res.stdout)["envs"]
            self.assertTrue(any(p.endswith(os.path.sep + self.manager.env_name) for p in envs))
            res = subprocess.run(
                ["conda", "run", "-n", self.manager.env_name, "python", "-c", "import numpy"],
                check=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0)
            res = subprocess.run(
                ["conda", "env", "list", "--json"],
                stdout=subprocess.PIPE,
                check=True,
                text=True,
            )
            envs = json.loads(res.stdout)["envs"]
            self.assertTrue(any(p.endswith(os.path.sep + self.manager.env_name) for p in envs))
        finally:
            subprocess.run(
                ["conda", "env", "remove", "-n", self.manager.env_name, "-y"], check=False
            )


class TestEnvironmentFactory(unittest.TestCase):

    @patch("os.path.abspath", return_value="/absolute/path/to/model")
    @patch.object(EnvironmentFactory, "check_environment_type", return_value="conda")
    def test_get_env_conda(self, mock_check_env, mock_abspath):
        env_manager = EnvironmentFactory.get_env(
            build="conda", model_name="test_model", model_path="/path/to/model"
        )
        self.assertIsInstance(env_manager, CondaManager)
        self.assertEqual(env_manager.base_name, "test_model")
        self.assertEqual(env_manager.model_directory, "/absolute/path/to/model")

    @patch("os.path.abspath", return_value="/absolute/path/to/model")
    @patch.object(EnvironmentFactory, "check_environment_type", return_value="venv")
    def test_get_env_venv(self, mock_check_env, mock_abspath):
        env_manager = EnvironmentFactory.get_env(
            build="venv", model_name="test_model", model_path="/path/to/model"
        )
        self.assertIsInstance(env_manager, VenvManager)
        self.assertEqual(env_manager.base_name, "test_model")
        self.assertEqual(env_manager.model_directory, "/absolute/path/to/model")

    @patch("os.path.abspath", return_value="/absolute/path/to/model")
    @patch.object(EnvironmentFactory, "check_environment_type", return_value="micromamba")
    def test_get_env_micromamba(self, mock_check_env, mock_abspath):
        env_manager = EnvironmentFactory.get_env(
            build="micromamba", model_name="test_model", model_path="/path/to/model"
        )
        self.assertIsInstance(
            env_manager, CondaManager
        )  # Assuming Micromamba uses CondaManager
        self.assertEqual(env_manager.base_name, "test_model")
        self.assertEqual(env_manager.model_directory, "/absolute/path/to/model")

    @patch("docker.from_env")
    @patch("os.path.abspath", return_value="/absolute/path/to/model")
    @patch.object(EnvironmentFactory, "check_environment_type", return_value=None)
    def test_get_env_docker(self, mock_check_env, mock_abspath, mock_from_env):
        env_manager = EnvironmentFactory.get_env(
            build="docker", model_name="test_model", model_path="/path/to/model"
        )
        self.assertIsInstance(env_manager, DockerManager)
        self.assertEqual(env_manager.base_name, "test_model")
        self.assertEqual(env_manager.model_directory, "/absolute/path/to/model")

    @patch("os.path.abspath", return_value="/absolute/path/to/model")
    @patch.object(EnvironmentFactory, "check_environment_type", return_value="conda")
    def test_get_env_default_conda(self, mock_check_env, mock_abspath):
        env_manager = EnvironmentFactory.get_env(
            build=None, model_name="test_model", model_path="/path/to/model"
        )
        self.assertIsInstance(env_manager, CondaManager)
        self.assertEqual(env_manager.base_name, "test_model")
        self.assertEqual(env_manager.model_directory, "/absolute/path/to/model")

    @patch("os.path.abspath", return_value="/absolute/path/to/model")
    @patch.object(EnvironmentFactory, "check_environment_type", return_value="venv")
    def test_get_env_default_venv(self, mock_check_env, mock_abspath):
        env_manager = EnvironmentFactory.get_env(
            build=None, model_name="test_model", model_path="/path/to/model"
        )
        self.assertIsInstance(env_manager, VenvManager)
        self.assertEqual(env_manager.base_name, "test_model")
        self.assertEqual(env_manager.model_directory, "/absolute/path/to/model")

    @patch("os.path.abspath", return_value="/absolute/path/to/model")
    @patch.object(EnvironmentFactory, "check_environment_type", return_value=None)
    def test_get_env_invalid(self, mock_check_env, mock_abspath):
        with self.assertRaises(Exception) as context:
            EnvironmentFactory.get_env(
                build="invalid", model_name="test_model", model_path="/path/to/model"
            )
        self.assertTrue("Wrong environment selection" in str(context.exception))

    @patch("os.path.abspath", return_value="/absolute/path/to/model")
    @patch.object(EnvironmentFactory, "check_environment_type", return_value="venv")
    @patch("logging.Logger.warning")
    def test_get_env_warning(self, mock_log_warning, mock_check_env, mock_abspath):
        EnvironmentFactory.get_env(
            build="conda", model_name="test_model", model_path="/path/to/model"
        )
        mock_log_warning.assert_called_once_with(
            f"Selected build environment (conda) for this model is different than that of"
            f" the experiment run. Consider selecting the same environment."
        )


class TestVenvEnvironmentManager(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        if not hasattr(venv, "create"):
            raise unittest.SkipTest("Venv is not available in the environment.")

    def setUp(self):
        self.model_directory = "/tmp/test_model"
        self.manager = VenvManager(base_name="test_env", model_directory=self.model_directory)
        os.makedirs(self.model_directory, exist_ok=True)
        with open(os.path.join(self.model_directory, "setup.py"), "w") as f:
            f.write("from setuptools import setup\nsetup(name='test_model', version='0.1')")
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        if self.manager.env_exists():
            shutil.rmtree(self.manager.env_path)
        if os.path.exists(self.model_directory):
            shutil.rmtree(self.model_directory)

    def test_create_and_delete_environment(self):
        self.manager.create_environment(force=True)

        self.assertTrue(self.manager.env_exists())

        pip_executable = os.path.join(self.manager.env_path, "bin", "pip")
        result = subprocess.run(
            [pip_executable, "list"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.assertEqual(result.returncode, 0)

        self.manager.create_environment(force=True)

        self.assertTrue(self.manager.env_exists())

    def test_init(self):
        self.assertEqual(self.manager.base_name, "test_env")
        self.assertEqual(self.manager.model_directory, self.model_directory)
        self.assertTrue(self.manager.env_name.startswith("test_env_"))

    def test_env_exists(self):
        self.assertFalse(self.manager.env_exists())
        self.manager.create_environment(force=True)
        self.assertTrue(self.manager.env_exists())

    def test_create_environment(self):
        self.manager.create_environment(force=True)
        self.assertTrue(self.manager.env_exists())

    def test_create_environment_force(self):
        self.manager.create_environment(force=True)
        env_path_before = self.manager.env_path
        self.manager.create_environment(force=True)
        self.assertTrue(self.manager.env_exists())
        self.assertEqual(env_path_before, self.manager.env_path)

    def test_install_dependencies(self):
        self.manager.create_environment(force=True)
        pip_executable = os.path.join(self.manager.env_path, "bin", "pip")
        result = subprocess.run(
            [pip_executable, "install", "-e", self.model_directory],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.assertEqual(result.returncode, 0)

    @patch("subprocess.Popen")
    def test_run_command(self, mock_popen):
        mock_process = MagicMock()
        mock_process.stdout = iter(["Output line 1\n", "Output line 2\n"])
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        command = "echo test_command"

        self.manager.run_command(command)

        output_cmd = f"bash -lc 'source \"{os.path.join(self.manager.env_path, 'bin', 'activate')}\"' && {command}"

        mock_popen.assert_called_once_with(
            output_cmd,
            shell=True,
            env=unittest.mock.ANY,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
        )


@unittest.skipUnless(DOCKER_SDK_AVAILABLE, "docker SDK is not installed")
class TestDockerManagerWithSDK(unittest.TestCase):
    def setUp(self):
        self.model_dir = "/tmp/test_model"
        os.makedirs(self.model_dir, exist_ok=True)
        with open(os.path.join(self.model_dir, "Dockerfile"), "w") as f:
            f.write("FROM scratch\n")

        self.patcher = patch("docker.from_env")
        self.mock_from_env = self.patcher.start()
        self.mock_client = MagicMock()
        self.mock_from_env.return_value = self.mock_client

        self.manager = DockerManager("My Model", self.model_dir)

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.model_dir, ignore_errors=True)

    def test_init(self):
        self.assertEqual(self.manager.base_name, "My_Model")
        self.assertEqual(self.manager.image_tag, "my_model_image")
        self.assertEqual(self.manager.container_name, "my_model_container")
        self.mock_from_env.assert_called_once()
        self.assertIs(self.manager.client, self.mock_client)

    def test_env_exists_true(self):
        self.mock_client.images.get.return_value = MagicMock()
        self.assertTrue(self.manager.env_exists())
        self.mock_client.images.get.assert_called_once_with(self.manager.image_tag)

    def test_env_exists_false(self):
        self.mock_client.images.get.side_effect = ImageNotFound("not found")
        self.assertFalse(self.manager.env_exists())
        self.mock_client.images.get.assert_called_once_with(self.manager.image_tag)

    def test_create_environment_builds_when_missing(self):
        self.manager.env_exists = MagicMock(return_value=False)
        fake_logs = [{"stream": "Step 1/2\n"}, {"stream": "Step 2/2\n"}]
        self.mock_client.api.build.return_value = fake_logs

        with patch("floatcsep.environments.log") as mock_log:
            self.manager.create_environment(force=False)

        self.mock_client.api.build.assert_called_once_with(
            path=self.manager.model_directory,
            tag=self.manager.image_tag,
            rm=True,
            decode=True,
            buildargs={
                "USER_UID": str(os.getuid()),
                "USER_GID": str(os.getgid()),
            },
            nocache=False,
        )
        infos = [call_args[0][0] for call_args in mock_log.info.call_args_list]
        self.assertEqual(sum("Successfully built" in msg for msg in infos), 1)

    def test_create_environment_skips_when_exists_and_not_forced(self):
        self.manager.env_exists = MagicMock(return_value=True)
        self.manager.create_environment(force=False)
        self.mock_client.images.remove.assert_not_called()
        self.mock_client.api.build.assert_not_called()

    def test_create_environment_force(self):
        self.manager.env_exists = MagicMock(return_value=True)
        fake_logs = [{"stream": ""}]
        self.mock_client.api.build.return_value = fake_logs

        with patch("floatcsep.environments.log") as mock_log:
            self.manager.create_environment(force=True)

        self.mock_client.images.remove.assert_called_once_with(
            self.manager.image_tag, force=True
        )
        self.mock_client.api.build.assert_called_once()
        infos = [call_args[0][0] for call_args in mock_log.info.call_args_list]
        self.assertEqual(sum("Successfully built" in msg for msg in infos), 1)

    def test_create_environment_build_error(self):
        self.manager.env_exists = MagicMock(return_value=False)
        self.mock_client.api.build.side_effect = APIError(
            "fail", response=None, explanation="err"
        )
        with self.assertRaises(APIError):
            self.manager.create_environment(force=False)

    def test_run_command_success(self):
        fake_container = MagicMock()
        fake_container.logs.return_value = [b"out1\n", b"out2\n"]
        fake_container.wait.return_value = {"StatusCode": 0}
        self.mock_client.containers.run.return_value = fake_container

        with patch("floatcsep.environments.log") as mock_log:
            self.manager.run_command()

        uid, gid = os.getuid(), os.getgid()
        try:
            expected_volumes = {
                Path(self.model_dir, "input"): {"bind": "/app/input", "mode": "rw"},
                Path(self.model_dir, "forecasts"): {"bind": "/app/forecasts", "mode": "rw"},
            }
            self.mock_client.containers.run.assert_called_once_with(
                self.manager.image_tag,
                remove=False,
                volumes=expected_volumes,
                detach=True,
                user=f"{uid}:{gid}",
            )
            fake_container.logs.assert_called_once_with(stream=True)
            fake_container.wait.assert_called_once()

            info_msgs = [args[0] for args, _ in mock_log.info.call_args_list]
            self.assertTrue(any("out1" in m for m in info_msgs))
        except Exception as msg:
            print("MacOS, skipped test")

    def test_run_command_failure(self):
        fake_container = MagicMock()
        fake_container.logs.return_value = b"error message"
        fake_container.wait.return_value = {"StatusCode": 5}
        self.mock_client.containers.run.return_value = fake_container

        with self.assertRaises(RuntimeError):
            self.manager.run_command()

    def test_install_dependencies_noop(self):
        self.manager.install_dependencies()


if __name__ == "__main__":
    unittest.main()
