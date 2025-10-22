import os
import shutil
import unittest
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, MagicMock
from dataclasses import dataclass, field
from floatcsep.infrastructure.registries import (
    ModelFileRegistry,
    ExperimentFileRegistry,
    FilepathMixin,
)


@dataclass
class DummyRegistry(FilepathMixin):
    workdir: str
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

    def test_rel_returns_relpath_to_workdir(self):
        r = self.registry.rel("catalogs", "cat1", "eventlist.txt")
        self.assertEqual(
            r.resolve(), Path(os.path.relpath(self.eventlist, self.tmpdir)).resolve()
        )
        self.assertFalse(str(r).startswith(str(self.tmpdir)))

    def test_rel_dir_returns_rel_directory(self):
        rdir = self.registry.rel_dir("catalogs", "cat1", "eventlist.txt")
        expected = Path(os.path.relpath(self.eventlist.parent, self.tmpdir))
        self.assertEqual(rdir.resolve(), expected.resolve())

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
