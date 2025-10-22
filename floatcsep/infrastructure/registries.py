import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime
from os.path import join, abspath, relpath, normpath, dirname, exists
from pathlib import Path
from typing import Sequence, Union, TYPE_CHECKING, Any, Optional

from floatcsep.utils.helpers import timewindow2str

if TYPE_CHECKING:
    from floatcsep.model import Model
    from floatcsep.evaluation import Evaluation

log = logging.getLogger("floatLogger")


class FilepathMixin:
    """
    Small mixin to provide filepath management functionality to Registries that uses files to
    store objects
    """

    workdir: Path
    path: Path

    @property
    def dir(self) -> Path:
        """
        Returns:
            The directory containing the model source.
        """

        return self.path.parents[0]

    @staticmethod
    def _parse_arg(arg) -> Union[str, list[str]]:
        if isinstance(arg, (list, tuple)):
            return timewindow2str(arg)
        elif isinstance(arg, str):
            return arg
        elif hasattr(arg, "name"):
            return arg.name
        elif hasattr(arg, "__name__"):
            return arg.__name__
        else:
            raise Exception("Arg is not found")

    def get_attr(self, *args: Sequence[str]) -> Path:
        """
        Access instance attributes and its contents (e.g., through dict keys) recursively in a
        normalized function call. Returns the expected absolute path of this element

        Args:
            *args: A sequence of keys (usually time-window strings)

        Returns:
            The registry element (forecast, catalogs, etc.) from a sequence of key value
            (usually time-window strings) as filepath
        """

        val = self.__dict__
        for i in args:
            parsed_arg = self._parse_arg(i)
            val = val[parsed_arg]
        return self.abs(val)

    def abs(self, *paths: Union[str | Path | Sequence[str | Path]]) -> Path:
        """
        Returns the absolute path of an object, relative to the Registry workdir.

        Args:
            *paths:

        Returns:

        """

        _path = Path(self.workdir, *[x for x in paths if x]).resolve()
        return _path

    def abs_dir(self, *paths: Sequence[str | Path]) -> Path:
        """
        Returns the absolute path of the directory containing an item relative to the Registry
        workdir.
        Args:
            *paths: sequence of keys (usually time-window strings)

        Returns:
            String describing the absolute directory
        """
        _path = Path(self.workdir, *paths).resolve()
        _dir = _path.parents[0]
        return _dir

    def rel(self, *paths: Union[Path | str | Sequence[str | Path]]) -> Path:
        """
        Gets the relative path of an item, relative to the Registry workdir

        Args:
            *paths: sequence of keys (usually time-window strings)
        Returns:
            String describing the relative path
        """

        _abspath = self.abs(*paths)
        _relpath = Path(relpath(_abspath, self.workdir))
        return _relpath

    def rel_dir(self, *paths: Sequence[str]) -> Path:
        """
        Gets the relative path of the directory containing an item, relative to the Registry
        workdir

        Args:
            *paths: sequence of keys (usually time-window strings)
        Returns:
            String describing the relative path
        """

        _path = self.abs(*paths)
        _dir = _path.parents[0]

        return Path(relpath(_dir, self.workdir))

    def file_exists(self, *args: Sequence[str | Path]):
        """
        Determine is such file exists in the filesystem

        Args:
            *paths: sequence of keys (usually time-window strings)
        Returns:
            flag indicating if file exists
        """
        file_abspath = self.get_attr(*args)
        return exists(file_abspath)


class ModelRegistry(ABC):
    @abstractmethod
    def get_input_catalog_key(self, tstring: str) -> str:
        pass

    @abstractmethod
    def get_forecast_key(self, tstring: str) -> str:
        pass

    @abstractmethod
    def get_args_key(self, tstring: str) -> str:
        pass

    @classmethod
    def factory(
        cls, registry_type: str = "file", **kwargs
    ) -> Union["ModelFileRegistry", "ModelHDF5Registry"]:
        """Factory method. Instantiate first on any explicit option provided in the model
        configuration.
        """
        if registry_type == "file":
            return ModelFileRegistry(**kwargs)

        elif registry_type == "hdf5":
            return ModelHDF5Registry(**kwargs)
        else:
            raise Exception("No valid model management schema was selected")


class ModelFileRegistry(ModelRegistry, FilepathMixin):
    def __init__(
        self,
        model_name: str,
        workdir: str,
        path: str,
        args_file: str = None,
        input_cat: str = None,
        fmt: str = None,
    ) -> None:
        """

        Args:
            model_name (str): Model's identifier string
            workdir (str): The current working directory of the experiment.
            path (str): The path of the model working directory (or model filepath).
            args_file (str): The path of the arguments file (only for TimeDependentModel).
            input_cat (str): : The path of the arguments file (only for TimeDependentModel).
        """

        self.model_name = model_name
        self.workdir = Path(workdir)
        self.path = self.abs(Path(path))

        self.args_file = args_file if args_file else None
        self.input_cat = input_cat if input_cat else None
        self.forecasts = {}
        self.input_args = {}
        self.input_cats = {}
        self.input_store = None
        self._fmt = fmt

    @property
    def fmt(self) -> str:
        """

        Returns:
            The extension or format of the forecast
        """
        fmt_ = self.path.suffix
        if fmt_:
            return fmt_
        else:
            return self._fmt

    def forecast_exists(self, timewindow: Union[str, list]) -> Union[bool, Sequence[bool]]:
        """
        Checks if forecasts exist for a sequence of time_windows

        Args:
            timewindow (str, list): A single or sequence of strings representing a time window

        Returns:
            A list of bool representing the existence of such forecasts.
        """
        if isinstance(timewindow, str):
            return self.file_exists("forecasts", timewindow)
        else:
            return [self.file_exists("forecasts", i) for i in timewindow]

    def get_input_catalog_key(self, *args: Sequence[str]) -> str:
        """
        Gets the filepath of the input catalog for a given sequence of keys (usually a timewindow
        string).

        Args:
            *args: A sequence of keys (usually time-window strings)

        Returns:
           The input catalog registry key from a sequence of key values
        """
        return self.get_attr("input_cats", *args).as_posix()

    def get_forecast_key(self, *args: Sequence[str]) -> str:
        """
        Gets the filepath of a forecast for a given sequence of keys (usually a timewindow
        string).

        Args:
            *args: A sequence of keys (usually time-window strings)

        Returns:
           The forecast registry from a sequence of key values
        """
        return self.get_attr("forecasts", *args).as_posix()

    def get_args_key(self, *args: Sequence[str]) -> str:
        """
        Gets the filepath of an arguments file for a given sequence of keys (usually a timewindow
        string).

        Args:
            *args: A sequence of keys (usually time-window strings)

        Returns:
           The argument file's key(s) from a sequence of key values
        """
        return self.get_attr("input_args", *args).as_posix()

    def build_tree(
        self,
        time_windows: Sequence[Sequence[datetime]] = None,
        model_class: str = "TimeIndependentModel",
        prefix: str = None,
        run_mode: str = "sequential",
        run_dir: Optional[str] = None,
    ) -> None:
        """
        Creates the run directory, and reads the file structure inside.

        Args:
            time_windows (list(str)): List of time windows or strings.
            model_class (str): Model's class name
            prefix (str): prefix of the model forecast filenames if TD
            run_mode (str): if run mode is sequential, input data (args and cat) will be
                dynamically overwritten in 'model/input/`  through time_windows. If 'parallel',
                input data is dynamically writing anew in
                'results/{time_window}/input/{model_name}/'.
            run_dir (str): Where experiment's results are stored.
        """

        windows = timewindow2str(time_windows)
        if model_class == "TimeIndependentModel":
            fname = self.path
            self.forecasts = {win: fname for win in windows}

        elif model_class == "TimeDependentModel":

            # grab names for creating model directories
            subfolders = ["input", "forecasts"]
            dirtree = {folder: self.abs(self.path, folder) for folder in subfolders}
            for _, folder_ in dirtree.items():
                os.makedirs(folder_, exist_ok=True)

            if run_mode == "sequential":
                self.input_args = {
                    win: Path(self.path, "input", self.args_file) for win in windows
                }
                self.input_cats = {
                    win: Path(self.path, "input", self.input_cat) for win in windows
                }
            elif run_mode == "parallel":
                self.input_args = {
                    win: Path(run_dir, win, "input", self.model_name, self.args_file)
                    for win in windows
                }
                self.input_cats = {
                    win: Path(run_dir, win, "input", self.model_name, self.input_cat)
                    for win in windows
                }

            self.forecasts = {
                win: Path(dirtree["forecasts"], f"{prefix}_{win}.{self.fmt}") for win in windows
            }

    def as_dict(self) -> dict:
        """

        Returns:
            Simple dictionary serialization of the instance with the core attributes
        """
        return {
            "workdir": self.workdir,
            "path": self.path,
            "args_file": self.args_file,
            "input_cat": self.input_cat,
            "forecasts": self.forecasts,
        }


class ModelHDF5Registry(ModelRegistry):

    def __init__(self, workdir: str, path: str):
        pass

    def get_input_catalog_key(self, tstring: str) -> str:
        return ""

    def get_forecast_key(self, tstring: str) -> str:
        return ""

    def get_args_key(self, tstring: str) -> str:
        return ""


class ExperimentRegistry(ABC):
    @abstractmethod
    def add_model_registry(self, model: "Model") -> None:
        pass

    @abstractmethod
    def get_model_registry(self, model_name: str) -> ModelRegistry:
        pass

    @abstractmethod
    def get_result_key(self, test_name: str, model_name: str, tstring: str) -> str:
        pass

    @abstractmethod
    def get_figure_key(self, test_name: str, model_name: str, tstring: str) -> str:
        pass

    @abstractmethod
    def get_test_catalog_key(self, tstring: str) -> str:
        pass

    @abstractmethod
    def build_tree(
        self,
        time_windows: Sequence[Sequence[datetime]],
        models: Sequence["Model"],
        tests: Sequence["Evaluation"],
    ) -> None:
        pass

    @classmethod
    def factory(
        cls, registry_type: str = "file", **kwargs
    ) -> Optional["ExperimentFileRegistry"]:
        """Factory method. Instantiate first on any explicit option provided in the experiment
        configuration.
        """

        if registry_type == "file":
            return ExperimentFileRegistry(**kwargs)
        else:
            return None


class ExperimentFileRegistry(ExperimentRegistry, FilepathMixin):
    """
    The class has the responsibility of managing the keys (based on models, timewindow and
    evaluation name strings) to the structure of the experiment inputs (catalogs, models etc)
    and results from the competing evaluations. It keeps track of the forecast registries, as
    well as the existence of results and their path in the filesystem.
    """

    def __init__(self, workdir: str, run_dir: str = "results") -> None:
        """

        Args:
            workdir: The working directory for the experiment run-time.
            run_dir: The directory in which the results will be stored.
        """
        self.workdir = Path(workdir)
        self.run_dir = self.abs(Path(run_dir))
        self.results = {}
        self.test_catalogs = {}
        self.figures = {}

        self.repr_config = "repr_config.yml"
        self.model_registries = {}

    def get_attr(self, *args: Any) -> Path:
        """
        Args:
            *args: A sequence of keys (usually models, tests and/or time-window strings)

        Returns:
            The filepath from a sequence of key values (usually models first, then time-window
            strings)
        """
        val = self.__dict__
        for i in args:
            parsed_arg = self._parse_arg(i)
            val = val[parsed_arg]

        return self.abs(self.run_dir, val)

    def add_model_registry(self, model: "Model") -> None:
        """
        Adds a model's ForecastRegistry to the ExperimentFileRegistry.

        Args:
            model (str): A Model object

        """
        self.model_registries[model.name] = model.registry

    def get_model_registry(self, model_name: str) -> None:
        """
        Retrieves a model's ForecastRegistry from the ExperimentFileRegistry.

        Args:
            model_name (str): The name of the model.

        Returns:
            ModelRegistry: The ModelRegistry associated with the model.
        """
        return self.model_registries.get(model_name)

    def result_exist(self, timewindow_str: str, test_name: str, model_name: str) -> bool:
        """
        Checks if a given test results exist

        Args:
            timewindow_str (str): String representing the time window
            test_name (str): Name of the evaluation
            model_name (str): Name of the model

        """
        return self.file_exists("results", timewindow_str, test_name, model_name)

    def get_test_catalog_key(self, *args: Sequence[any]) -> str:
        """
        Gets the file path of a testing catalog.

        Args:
            *args: A sequence of keys (time-window strings)

        Returns:
            The filepath of the testing catalog for a given time-window
        """
        val = self.test_catalogs
        for i in args:
            parsed_arg = self._parse_arg(i)
            val = val[parsed_arg]

        return self.abs(self.run_dir, val).as_posix()

    def get_result_key(self, *args: Sequence[any]) -> str:
        """
        Gets the file path of an evaluation result.

        Args:
            args: A sequence of keys (usually models, tests and/or time-window strings)

        Returns:
            The filepath of a serialized result
        """
        val = self.results
        for i in args:
            parsed_arg = self._parse_arg(i)
            val = val[parsed_arg]
        return self.abs(self.run_dir, val).as_posix()

    def get_figure_key(self, *args: Sequence[any]) -> Path:
        """
        Gets the file path of a result figure.

        Args:
            *args: A sequence of keys (usually tests and/or time-window strings)

        Returns:
            The filepath of the figure for a given result
        """
        val = self.figures
        for i in args:
            parsed_arg = self._parse_arg(i)
            val = val[parsed_arg]
        return self.abs(self.run_dir, val).as_posix()

    def build_tree(
        self,
        time_windows: Sequence[Sequence[datetime]],
        models: Sequence["Model"],
        tests: Sequence["Evaluation"],
        run_mode: str = "sequential",
    ) -> None:
        """
        Creates the run directory and reads the file structure inside.

        Args:
            time_windows: List of time windows, or representing string.
            models: List of models or model names
            tests: List of tests or test names
            run_mode: 'parallel' or 'sequential'

        """
        windows = timewindow2str(time_windows)

        models = [i.name for i in models]
        tests = [i.name for i in tests]

        run_folder = self.run_dir
        subfolders = ["catalog", "evaluations", "figures"]
        if run_mode == "parallel":
            subfolders.append("input")
        dirtree = {
            win: {folder: self.abs(run_folder, win, folder) for folder in subfolders}
            for win in windows
        }

        # create directories if they don't exist
        for tw, tw_folder in dirtree.items():
            for _, folder_ in tw_folder.items():
                os.makedirs(folder_, exist_ok=True)
                if run_mode == "parallel" and folder_.name == "input":
                    for model in models:
                        os.makedirs(join(folder_, model), exist_ok=True)
        results = {
            win: {
                test: {
                    model: join(win, "evaluations", f"{test}_{model}.json") for model in models
                }
                for test in tests
            }
            for win in windows
        }
        test_catalogs = {win: join(win, "catalog", "test_catalog.json") for win in windows}

        figures = {
            "main_catalog_map": "catalog",
            "main_catalog_time": "events",
            **{
                win: {
                    **{test: join(win, "figures", f"{test}") for test in tests},
                    "catalog_map": join(win, "figures", "catalog_map"),
                    "catalog_time": join(win, "figures", "catalog_time"),
                    "forecasts": {
                        model: join(win, "figures", f"forecast_{model}") for model in models
                    },
                }
                for win in windows
            },
        }

        self.results = results
        self.test_catalogs = test_catalogs
        self.figures = figures

    def as_dict(self) -> Path:

        return self.workdir
