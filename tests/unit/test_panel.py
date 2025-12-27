import os
import unittest
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from floatcsep.postprocess.panel.manifest import _rel, _timedelta_to_str, build_manifest
from floatcsep.postprocess.panel.views.utils import (
    make_doi_badge,
    fmt_coord,
    lonlat_to_mercator,
    build_region_basemap,
    parse_time_window_strings,
    build_time_windows_figure,
)


class _Cell:
    def __init__(self, pts):
        self.points = np.asarray(pts, dtype=float)


class _Region:
    def __init__(self, polys, dh=0.1):
        self.polygons = polys
        self.dh = dh

    def get_bbox(self):
        xs = []
        ys = []
        for p in self.polygons:
            xs.extend(p.points[:, 0].tolist())
            ys.extend(p.points[:, 1].tolist())
        return min(xs), max(xs), min(ys), max(ys)


class _ModelRegistry:
    def __init__(self, root: Path, name: str):
        self._root = root
        self._name = name
        self.path = root / "models" / name

    def get_forecast_key(self, tw_obj):
        return self._root / "forecasts" / f"{self._name}_{tw_obj}.csv"

    def rel(self, p):
        return os.path.relpath(str(p), str(self._root)).replace("\\", "/")


class _Repo:
    pass


class _Model:
    def __init__(self, root: Path, name: str):
        self.name = name
        self.registry = _ModelRegistry(root, name)
        self.repository = _Repo()
        self.forecast_unit = "days"
        self.giturl = None
        self.repo_hash = "abc"
        self.zenodo_id = None
        self.authors = ["x", "y"]
        self.doi = "10.5281/zenodo.1"
        self.func = None
        self.func_kwargs = None
        self.fmt = "csv"


class _Test:
    def __init__(self, name):
        self.name = name

        def f():
            return None

        self.func = f
        self.func_kwargs = {"a": 1}
        self.ref_model = None
        self.plot_func = None
        self.plot_args = None
        self.plot_kwargs = None


class _CatRepo:
    def __init__(self, cat_path: Path):
        self.cat_path = cat_path


class _Registry:
    def __init__(self, root: Path, exists=None, fail_catalog=False):
        self._root = root
        self.run_dir = Path("results")
        self._exists = set(exists or [])
        self._fail_catalog = fail_catalog

    def abs(self, p):
        return self._root / Path(p)

    def file_exists(self, kind, tw_obj, name):
        return (str(tw_obj), str(name)) in self._exists

    def get_figure_key(self, *args):
        if len(args) == 1 and isinstance(args[0], str):
            if self._fail_catalog:
                raise RuntimeError("nope")
            key = args[0]
            return self._root / "figures" / f"{key}.png"

        if len(args) == 2:
            tw_obj, key = args
            return self._root / "figures" / f"{tw_obj}__{key}.png"

        raise ValueError("bad args")


class TestPanel(unittest.TestCase):
    def test_a(self):
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            p = base / "a" / "b" / "c.txt"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")

            out = _rel(str(p), str(base))
            self.assertEqual(out, "a/b/c.txt")

    def test_b(self):
        self.assertIsNone(_timedelta_to_str(None))
        self.assertEqual(_timedelta_to_str("1 year"), "1 year")
        self.assertEqual(_timedelta_to_str(timedelta(days=365)), "1 year")
        self.assertEqual(_timedelta_to_str(timedelta(days=730)), "2 years")
        self.assertEqual(_timedelta_to_str(timedelta(days=2)), "2 days")
        self.assertEqual(_timedelta_to_str(timedelta(hours=3)), "3 hours")
        self.assertEqual(_timedelta_to_str(timedelta(days=1, seconds=3600)), str(timedelta(days=1, seconds=3600)))

    def test_c(self):
        s = make_doi_badge(" 10.5281/zenodo.123 ")
        self.assertIn("https://doi.org/10.5281/zenodo.123", s)
        self.assertIn("zenodo.org/badge/DOI/10.5281/zenodo.123.svg", s)

    def test_d(self):
        self.assertEqual(fmt_coord(None), "?")
        self.assertEqual(fmt_coord(1.23456, ndigits=3), "1.235")
        self.assertEqual(fmt_coord(1.2000, ndigits=3), "1.2")
        self.assertEqual(fmt_coord("x"), "x")

    def test_e(self):
        x, y = lonlat_to_mercator(0.0, 0.0)
        self.assertAlmostEqual(x, 0.0, places=6)
        self.assertAlmostEqual(y, 0.0, places=6)

    def test_f(self):
        """Mix valid and invalid inputs; only valid ones should survive."""
        out = parse_time_window_strings(
            [
                "2020-01-01 to 2020-01-31",
                "bad",
                "2020-02-01 to nope",
                "2020-02-01 to 2020-02-02",
            ]
        )
        self.assertEqual(len(out), 2)
        self.assertEqual(out[0]["label"], "Window 1")
        self.assertEqual(out[0]["length_days"], 30)
        self.assertEqual(out[1]["label"], "Window 4")
        self.assertEqual(out[1]["length_days"], 1)

    def test_g(self):
        fig = build_time_windows_figure([], height=123)
        self.assertEqual(fig.height, 123)
        self.assertEqual(fig.title.text, "No time windows defined")

    def test_h(self):
        now = datetime.today()
        a = {"label": "Window 1", "start": now - timedelta(days=2), "end": now + timedelta(days=2),
             "start_str": (now - timedelta(days=2)).date().isoformat(),
             "end_str": (now + timedelta(days=2)).date().isoformat(),
             "length_days": 4}
        b = {"label": "Window 2", "start": now - timedelta(days=1), "end": now + timedelta(days=1),
             "start_str": (now - timedelta(days=1)).date().isoformat(),
             "end_str": (now + timedelta(days=1)).date().isoformat(),
             "length_days": 2}
        fig = build_time_windows_figure([a, b], height=200)
        self.assertEqual(fig.height, 200)
        self.assertTrue(len(fig.renderers) > 0)

    def test_i(self):
        fig, n_cells, dh, bx, by = build_region_basemap(None)
        self.assertIsNotNone(fig)
        self.assertIsNone(n_cells)
        self.assertIsNone(dh)
        self.assertEqual(bx, (None, None))
        self.assertEqual(by, (None, None))

    def test_j(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cell1 = _Cell([(0, 0), (0, 1), (1, 1), (1, 0)])
            cell2 = _Cell([(1, 0), (1, 1), (2, 1), (2, 0)])
            region = _Region([cell1, cell2], dh=0.5)

            fig, n_cells, dh, bx, by = build_region_basemap(region, plot_cells=True, min_height=111)
            self.assertIsNotNone(fig)
            self.assertEqual(n_cells, 2)
            self.assertEqual(dh, 0.5)
            self.assertEqual(bx, [0.0, 2.0])
            self.assertEqual(by, [0.0, 1.0])
            self.assertGreaterEqual(fig.min_height, 111)

    def test_k(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "figures").mkdir(parents=True, exist_ok=True)
            (root / "forecasts").mkdir(parents=True, exist_ok=True)

            for nm in ["main_catalog_map", "main_catalog_time"]:
                (root / "figures" / f"{nm}.png").write_text("x")

            (root / "figures" / "tw1__T1.png").write_text("x")
            (root / "figures" / "tw1__T1_M1.png").write_text("x")

            reg = _Registry(root, exists={("tw1", "T1_M1")})
            cat_repo = _CatRepo(Path("cats") / "main.csv")
            m1 = _Model(root, "M1")
            m2 = _Model(root, "M2")
            t1 = _Test("T1")

            exp = SimpleNamespace(
                registry=reg,
                catalog_repo=cat_repo,
                name="x",
                start_date=datetime(2020, 1, 1),
                end_date=datetime(2020, 2, 1),
                authors=["a", "b"],
                doi="d",
                journal="j",
                manuscript_doi=None,
                exp_time="t",
                floatcsep_version="v1",
                pycsep_version="v2",
                last_run="now",
                catalog_doi="cd",
                LICENSE="MIT",
                magnitudes=[1.0, 2.0],
                region=None,
                time_windows=["tw1", "tw2"],
                models=[m1, m2],
                tests=[t1],
                time_config={
                    "exp_class": "td",
                    "intervals": 2,
                    "horizon": timedelta(days=365),
                    "offset": timedelta(days=2),
                    "growth": "incremental",
                },
                region_config={},
                exp_class="td",
                run_mode="sequential",
                run_dir="results",
                config_file="config.yml",
                model_config="models.yml",
                test_config="tests.yml",
                mag_min=1.0,
                mag_max=2.0,
                mag_bin=0.1,
                depth_min=-2.0,
                depth_max=30.0,
            )

            tw_map = {"tw1": "2020-01-01_2020-01-31", "tw2": "2020-02-01_2020-02-28"}

            def fake_t2s(x):
                return tw_map[x]

            with patch("floatcsep.postprocess.panel.manifest.timewindow2str", new=fake_t2s):
                man = build_manifest(exp, app_root=str(root))

            self.assertEqual(man.name, "x")
            self.assertEqual(man.start_date, "2020-01-01")
            self.assertEqual(man.end_date, "2020-02-01")
            self.assertEqual(man.authors, "a, b")
            self.assertEqual(man.exp_class, "Time-Dependent")
            self.assertEqual(man.n_intervals, 2)
            self.assertEqual(man.horizon, "1 year")
            self.assertEqual(man.offset, "2 days")

            self.assertIn("path", man.catalog)
            self.assertIn("map", man.catalog)
            self.assertIn("time", man.catalog)

            tw1s = "2020-01-01 to 2020-01-31"
            self.assertIn((tw1s, "T1"), man.results_main)
            self.assertIn((tw1s, "T1", "M1"), man.results_model)
            self.assertNotIn((tw1s, "T1", "M2"), man.results_model)

            names = [m["name"] for m in man.models]
            self.assertEqual(set(names), {"M1", "M2"})
            self.assertIn(tw1s, man.models[0]["forecasts"])
            self.assertIn(tw1s, man.models[1]["forecasts"])

    def test_l(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "figures").mkdir(parents=True, exist_ok=True)
            (root / "forecasts").mkdir(parents=True, exist_ok=True)

            reg = _Registry(root, fail_catalog=True)
            cat_repo = _CatRepo(Path("cats") / "main.csv")
            m1 = _Model(root, "M1")
            t1 = _Test("T1")

            exp = SimpleNamespace(
                registry=reg,
                catalog_repo=cat_repo,
                name="x",
                start_date=datetime(2020, 1, 1),
                end_date=datetime(2020, 1, 2),
                authors="a",
                doi=None,
                journal=None,
                manuscript_doi=None,
                exp_time=None,
                floatcsep_version=None,
                pycsep_version=None,
                last_run=None,
                catalog_doi=None,
                LICENSE=None,
                magnitudes=[],
                region=None,
                time_windows=["tw1"],
                models=[m1],
                tests=[t1],
                time_config={},
                region_config={},
            )

            with patch("floatcsep.postprocess.panel.manifest.timewindow2str", new=lambda x: "2020-01-01_2020-01-02"):
                man = build_manifest(exp, app_root=str(root))

            self.assertIsInstance(man.catalog, dict)
            self.assertEqual(man.catalog, {})


if __name__ == "__main__":
    unittest.main()
