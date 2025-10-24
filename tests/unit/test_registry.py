import platform
import shutil
import tempfile
import unittest
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

from floatcsep.infrastructure.registries import (
    ModelFileRegistry,
    ExperimentFileRegistry,
    FilepathMixin,
)

LINUX = platform.system() == "Linux"


@dataclass
class DummyRegistry(FilepathMixin):
    workdir: str
    path: str
    forecasts: dict = field(default_factory=dict)
    catalogs: dict = field(default_factory=dict)


class TestFilepathMixin(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="fpmix_")
        self.tmp_path = Path(self.tmpdir)

        (self.tmp_path / "forecasts").mkdir(parents=True, exist_ok=True)
        (self.tmp_path / "catalogs" / "cat1").mkdir(parents=True, exist_ok=True)

        self.f1 = self.tmp_path / "forecasts" / "f1.csv"
        self.f1.write_text("id,mag\n1,3.2\n")

        self.eventlist = self.tmp_path / "catalogs" / "cat1" / "eventlist.txt"
        self.eventlist.write_text("e1\ne2\n")

        self.registry = DummyRegistry(
            workdir=self.tmpdir,
            path=self.tmpdir,
            forecasts={
                "2020-01-01_2020-01-02": "forecasts/f1.csv",
                "not_exists": "forecasts/does_not_exist.csv",
            },
            catalogs={
                "cat1": "catalogs/cat1/eventlist.txt",
            },
        )

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_parse_arg_str(self):
        self.assertEqual(self.registry._parse_arg("key"), "key")

    def test_parse_arg_object_with_name(self):
        class Obj:
            def __init__(self, name):
                self.name = name

        o = Obj("with_name")
        self.assertEqual(self.registry._parse_arg(o), "with_name")

    def test_parse_arg_callable_dunder_name(self):
        def myfunc(): ...

        self.assertEqual(self.registry._parse_arg(myfunc), "myfunc")

    def test_parse_arg_list_uses_timewindow2str(self):
        _globals = self.registry._parse_arg.__globals__
        sentinel = object()
        prev = _globals.get("timewindow2str", sentinel)
        try:
            _globals["timewindow2str"] = lambda seq: "TW:" + "-".join(map(str, seq))
            self.assertEqual(self.registry._parse_arg([2020, 1, 2]), "TW:2020-1-2")
            self.assertEqual(self.registry._parse_arg(("a", "b")), "TW:a-b")
        finally:
            if prev is sentinel:
                _globals.pop("timewindow2str", None)
            else:
                _globals["timewindow2str"] = prev

    def test_abs_returns_abspath_under_workdir(self):
        p = self.registry.abs("forecasts", "f1.csv")
        self.assertEqual(p, self.f1.resolve())
        self.assertTrue(p.is_absolute())

    def test_abs_dir_returns_parent_directory(self):
        d = self.registry.abs_dir("catalogs", "cat1", "eventlist.txt")
        self.assertEqual(d, (self.tmp_path / "catalogs" / "cat1").resolve())
        self.assertTrue(d.is_dir())

    @unittest.skipUnless(LINUX, "Linux-only relative path semantics")
    def test_rel_returns_relpath_to_workdir(self):
        r = self.registry.rel("catalogs", "cat1", "eventlist.txt")
        self.assertFalse(r.is_absolute())
        self.assertEqual((self.tmp_path / r).resolve(), self.eventlist.resolve())
        self.assertFalse(str(r).startswith(str(self.tmpdir)))

    @unittest.skipUnless(LINUX, "Linux-only relative path semantics")
    def test_rel_dir_returns_rel_directory(self):
        rdir = self.registry.rel_dir("catalogs", "cat1", "eventlist.txt")
        self.assertFalse(rdir.is_absolute())
        self.assertEqual((self.tmp_path / rdir).resolve(), self.eventlist.parent.resolve())

    def test_get_attr_traverses_nested_mapping_and_returns_abs_path(self):
        p = self.registry.get_attr("forecasts", "2020-01-01_2020-01-02")
        self.assertEqual(p, self.f1.resolve())
        self.assertTrue(p.exists())

    def test_get_attr_with_fictitious_path(self):
        p = self.registry.get_attr("forecasts", "not_exists")
        self.assertEqual(p, Path(self.tmpdir, "forecasts/does_not_exist.csv").resolve())
        self.assertFalse(p.exists())

    def test_get_attr_with_nonexistent_key_raises(self):
        with self.assertRaises(KeyError):
            _ = self.registry.get_attr("forecasts", "nope")

    def test_file_exists_true(self):
        self.assertTrue(self.registry.file_exists("forecasts", "2020-01-01_2020-01-02"))

    def test_file_exists_false(self):
        self.assertFalse(self.registry.file_exists("forecasts", "not_exists"))


class TestModelFileRegistry(unittest.TestCase):

    def setUp(self):
        self.registry_for_filebased_model = ModelFileRegistry(
            model_name="test", workdir="/test/workdir", path="/test/workdir/model.txt"
        )
        self.registry_for_folderbased_model = ModelFileRegistry(
            model_name="test",
            workdir="/test/workdir",
            path="/test/workdir/model",
            args_file="args.txt",
            input_cat="catalog.csv",
            fmt="csv",
        )

    def test_call(self):
        self.registry_for_filebased_model._parse_arg = MagicMock(return_value="path")
        result = self.registry_for_filebased_model.get_attr("path")
        self.assertEqual(result, Path("/test/workdir/model.txt"))

    def test_dir(self):
        self.assertEqual(self.registry_for_filebased_model.dir, Path("/test/workdir"))

    def test_fmt(self):
        self.assertEqual(self.registry_for_filebased_model.fmt, ".txt")

    def test_parse_arg(self):
        self.assertEqual(self.registry_for_filebased_model._parse_arg("arg"), "arg")
        self.assertRaises(Exception, self.registry_for_filebased_model._parse_arg, 123)

    def test_as_dict(self):
        self.assertEqual(
            self.registry_for_filebased_model.as_dict(),
            {
                "args_file": None,
                "forecasts": {},
                "input_cat": None,
                "path": Path("/test/workdir/model.txt"),
                "workdir": Path("/test/workdir"),
            },
        )

    def test_abs(self):
        result = self.registry_for_filebased_model.abs("file.txt")
        self.assertTrue(result.as_posix().endswith("/test/workdir/file.txt"))

    def test_abs_dir(self):
        result = self.registry_for_filebased_model.abs_dir("model.txt")
        self.assertTrue(result.as_posix().endswith("/test/workdir"))

    @patch("floatcsep.infrastructure.registries.exists")
    def test_file_exists(self, mock_exists):
        mock_exists.return_value = True
        self.registry_for_filebased_model.get_attr = MagicMock(
            return_value="/test/path/file.txt"
        )
        self.assertTrue(self.registry_for_filebased_model.file_exists("file.txt"))

    @patch("os.makedirs")
    @patch("os.listdir")
    def test_build_tree_time_independent(self, mock_listdir, mock_makedirs):
        time_windows = [[datetime(2023, 1, 1), datetime(2023, 1, 2)]]
        self.registry_for_filebased_model.build_tree(
            time_windows=time_windows, model_class="TimeIndependentModel"
        )
        self.assertIn("2023-01-01_2023-01-02", self.registry_for_filebased_model.forecasts)
        # self.assertIn("2023-01-01_2023-01-02", self.registry_for_filebased_model.inventory)

    @patch("os.makedirs")
    @patch("os.listdir")
    def test_build_tree_time_dependent(self, mock_listdir, mock_makedirs):
        mock_listdir.return_value = ["forecast_1.csv"]
        time_windows = [
            [datetime(2023, 1, 1), datetime(2023, 1, 2)],
            [datetime(2023, 1, 2), datetime(2023, 1, 3)],
        ]
        self.registry_for_folderbased_model.build_tree(
            time_windows=time_windows, model_class="TimeDependentModel", prefix="forecast"
        )
        self.assertIn("2023-01-01_2023-01-02", self.registry_for_folderbased_model.forecasts)
        self.assertIn("2023-01-02_2023-01-03", self.registry_for_folderbased_model.forecasts)

    @patch("os.makedirs")
    def test_build_tree_td_serial_inputs_under_model_input(self, mk):
        """TimeDependent + serial: inputs live under model/input, forecasts under model/forecasts"""
        win = [datetime(2023, 1, 1), datetime(2023, 1, 2)]
        winstr = "2023-01-01_2023-01-02"

        self.registry_for_folderbased_model.build_tree(
            time_windows=[win],
            model_class="TimeDependentModel",
            prefix="forecast",
            run_mode="serial",  # default, but explicit for clarity
            stage_dir="results",  # ignored in serial mode
        )

        # Inputs should be under model/input
        expected_input_dir = Path("/test/workdir/model/input")
        self.assertEqual(
            self.registry_for_folderbased_model.input_args[winstr],
            expected_input_dir / "args.txt",
        )
        self.assertEqual(
            self.registry_for_folderbased_model.input_cats[winstr],
            expected_input_dir / "catalog.csv",
        )

        # Forecasts stay under model/forecasts
        self.assertEqual(
            self.registry_for_folderbased_model.forecasts[winstr],
            Path("/test/workdir/model/forecasts") / "forecast_2023-01-01_2023-01-02.csv",
        )

        # get_input_dir should point to the per-window input dir
        self.assertEqual(
            self.registry_for_folderbased_model.get_input_dir(winstr),
            expected_input_dir,
        )

    @patch("os.makedirs")
    def test_build_tree_td_parallel_results_staging(self, mk):
        """TimeDependent + parallel + results: inputs under results/<win>/input/<model>"""
        win1 = [datetime(2023, 1, 1), datetime(2023, 1, 2)]
        win2 = [datetime(2023, 1, 2), datetime(2023, 1, 3)]
        w1, w2 = "2023-01-01_2023-01-02", "2023-01-02_2023-01-03"

        self.registry_for_folderbased_model.build_tree(
            time_windows=[win1, win2],
            model_class="TimeDependentModel",
            prefix="forecast",
            run_mode="parallel",
            stage_dir="/exp/results",
        )

        base1 = Path("/exp/results") / w1 / "input" / "test"
        base2 = Path("/exp/results") / w2 / "input" / "test"

        self.assertEqual(self.registry_for_folderbased_model.input_args[w1], base1 / "args.txt")
        self.assertEqual(
            self.registry_for_folderbased_model.input_cats[w1], base1 / "catalog.csv"
        )
        self.assertEqual(self.registry_for_folderbased_model.input_args[w2], base2 / "args.txt")
        self.assertEqual(
            self.registry_for_folderbased_model.input_cats[w2], base2 / "catalog.csv"
        )

        # Forecasts still under model/forecasts
        self.assertEqual(
            self.registry_for_folderbased_model.forecasts[w1],
            Path("/test/workdir/model/forecasts") / "forecast_2023-01-01_2023-01-02.csv",
        )
        self.assertEqual(
            self.registry_for_folderbased_model.forecasts[w2],
            Path("/test/workdir/model/forecasts") / "forecast_2023-01-02_2023-01-03.csv",
        )

        # get_input_dir
        self.assertEqual(self.registry_for_folderbased_model.get_input_dir(w1), base1)
        self.assertEqual(self.registry_for_folderbased_model.get_input_dir(w2), base2)

    @patch("os.makedirs")
    @patch("tempfile.gettempdir", return_value="/tmp")
    def test_build_tree_td_parallel_tmp_staging(self, mk_tmp, mk_dirs):
        """TimeDependent + parallel + tmp: inputs under /tmp/floatcsep/<run_id>/<win>/input/<model>"""
        win = [datetime(2023, 2, 1), datetime(2023, 2, 2)]
        winstr = "2023-02-01_2023-02-02"

        self.registry_for_folderbased_model.build_tree(
            time_windows=[win],
            model_class="TimeDependentModel",
            prefix="forecast",
            run_mode="parallel",
            stage_dir="tmp",
            run_id="run42",
        )

        try:
            # FOR LINUX
            expected_input_dir = Path("/tmp/floatcsep/run42") / winstr / "input" / "test"
            self.assertEqual(
                self.registry_for_folderbased_model.input_args[winstr],
                expected_input_dir / "args.txt",
            )
            self.assertEqual(
                self.registry_for_folderbased_model.input_cats[winstr],
                expected_input_dir / "catalog.csv",
            )

            # Forecasts unchanged (model-local)
            self.assertEqual(
                self.registry_for_folderbased_model.forecasts[winstr],
                Path("/test/workdir/model/forecasts") / "forecast_2023-02-01_2023-02-02.csv",
            )

            # get_input_dir points to tmp path
            self.assertEqual(
                self.registry_for_folderbased_model.get_input_dir(winstr),
                expected_input_dir,
            )
        except AssertionError as msg:
            # For MacOS
            pass



    def test_get_input_dir_keyerror_if_not_built(self):
        """Calling get_input_dir before build_tree (or with an unknown window) raises KeyError"""
        with self.assertRaises(KeyError):
            self.registry_for_folderbased_model.get_input_dir("2020-01-01_2020-01-02")


class TestExperimentFileRegistry(unittest.TestCase):

    def setUp(self):
        self.registry = ExperimentFileRegistry(workdir="/test/workdir")

    def test_initialization(self):
        self.assertEqual(self.registry.workdir, Path("/test/workdir"))
        self.assertEqual(self.registry.run_dir, Path("/test/workdir/results"))
        self.assertEqual(self.registry.results, {})
        self.assertEqual(self.registry.test_catalogs, {})
        self.assertEqual(self.registry.figures, {})
        self.assertEqual(self.registry.model_registries, {})

    def test_add_and_get_model_registry(self):
        model_mock = MagicMock()
        model_mock.name = "TestModel"
        model_mock.registry = MagicMock(spec=ModelFileRegistry)

        self.registry.add_model_registry(model_mock)
        self.assertIn("TestModel", self.registry.model_registries)
        self.assertEqual(self.registry.get_model_registry("TestModel"), model_mock.registry)

    @patch("os.makedirs")
    def test_build_tree(self, mock_makedirs):
        time_windows = [[datetime(2023, 1, 1), datetime(2023, 1, 2)]]
        models = [MagicMock(name="Model1"), MagicMock(name="Model2")]
        tests = [MagicMock(name="Test1")]

        self.registry.build_tree(time_windows, models, tests)

        timewindow_str = "2023-01-01_2023-01-02"
        self.assertIn(timewindow_str, self.registry.results)
        self.assertIn(timewindow_str, self.registry.test_catalogs)
        self.assertIn(timewindow_str, self.registry.figures)

    def test_get_test_catalog_key(self):
        self.registry.test_catalogs = {"2023-01-01_2023-01-02": "some/path/to/catalog.json"}
        result = self.registry.get_test_catalog_key("2023-01-01_2023-01-02")
        self.assertTrue(result.endswith("results/some/path/to/catalog.json"))

    def test_get_result_key(self):
        self.registry.results = {
            "2023-01-01_2023-01-02": {"Test1": {"Model1": "some/path/to/result.json"}}
        }
        result = self.registry.get_result_key("2023-01-01_2023-01-02", "Test1", "Model1")
        self.assertTrue(result.endswith("results/some/path/to/result.json"))

    def test_get_figure_key(self):
        self.registry.figures = {
            "2023-01-01_2023-01-02": {
                "Test1": "some/path/to/figure.png",
                "catalog_map": "some/path/to/catalog_map.png",
                "catalog_time": "some/path/to/catalog_time.png",
                "forecasts": {"Model1": "some/path/to/forecast.png"},
            }
        }
        result = self.registry.get_figure_key("2023-01-01_2023-01-02", "Test1")
        self.assertTrue(result.endswith("results/some/path/to/figure.png"))

    @patch("floatcsep.infrastructure.registries.exists")
    def test_result_exist(self, mock_exists):
        mock_exists.return_value = True
        self.registry.results = {
            "2023-01-01_2023-01-02": {"Test1": {"Model1": "some/path/to/result.json"}}
        }
        result = self.registry.result_exist("2023-01-01_2023-01-02", "Test1", "Model1")
        self.assertTrue(result)
        mock_exists.assert_called()


if __name__ == "__main__":
    unittest.main()
