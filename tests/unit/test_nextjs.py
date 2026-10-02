import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from floatcsep.postprocess.nextjs import manifest_api, runtime, schemas
from floatcsep.postprocess.nextjs.schemas import external_models

WINDOWS = ["2000-01-01 to 2001-01-01", "2000-01-01 to 2002-01-01"]
GRID = {
    "name": "G",
    "lon0": 0.0,
    "lat0": 0.0,
    "dh": 1.0,
    "nx": 4,
    "ny": 3,
    "order": "lon-major",
}


class TestExternalForecasts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.rates = np.random.default_rng(3).gamma(1.0, 1e-3, (12, 2))  # 4 x 3 cells, 2 bins
        np.save(self.dir / "a.npy", self.rates)

    def tearDown(self):
        self.tmp.cleanup()

    def declare(self, magnitudes=(5.0, 5.1), **grid):
        declaration = self.dir / "external_forecasts.json"
        spec = {
            "grid": {**GRID, **grid},
            "magnitudes": list(magnitudes) if magnitudes is not None else None,
            "forecast_unit": 1,
            "forecasts": {"A": "a.npy"},
        }
        declaration.write_text(json.dumps(spec))
        return declaration

    def write_manifest(self):
        manifest = self.dir / "manifest.json"
        models = external_models(self.declare(), WINDOWS)
        manifest.write_text(
            json.dumps({"models": models, "time_windows": WINDOWS, "app_root": str(self.dir)})
        )
        return str(manifest)

    def test_models(self):
        (model,) = external_models(self.declare(), WINDOWS)
        self.assertEqual(model["name"], "A=G")
        self.assertEqual(set(model["forecasts"]), set(WINDOWS))
        self.assertEqual(model["path"], str((self.dir / "a.npy").resolve()))
        self.assertEqual(model["external"]["grid"]["nx"], 4)

    def test_grids_are_normalised_as_the_dashboard_reads_them(self):
        (model,) = external_models(self.declare(nx=4.0, lon0=-180, name=7), WINDOWS)
        self.assertEqual(
            model["external"]["grid"],
            {
                "name": "7",
                "lon0": -180.0,
                "lat0": 0.0,
                "dh": 1.0,
                "nx": 4,
                "ny": 3,
                "order": "lon-major",
            },
        )
        self.assertIsInstance(model["external"]["grid"]["nx"], int)

    def test_grids_a_browser_cannot_map_are_skipped(self):
        for grid in (
            {"nx": 70000},
            {"nx": 65535, "ny": 65535},
            {"dh": 0},
            {"nx": 3.5},
            {"nx": True},
            {"lon0": "-180"},
            {"dh": float("nan")},
            {"lat0": None},
            {"order": "lat-major"},
            {"magnitudes": ["5.0"]},
        ):
            # Other tests reconfigure logging, so the warning is checked on the logger itself
            with self.subTest(grid=grid), patch.object(schemas.logger, "warning") as warn:
                magnitudes = grid.pop("magnitudes", (5.0, 5.1))
                self.assertEqual(external_models(self.declare(magnitudes, **grid), WINDOWS), [])
                warn.assert_called_once()

    def test_sums_are_computed_once_for_all_windows(self):
        manifest = self.write_manifest()
        cache = self.dir / "cache"
        with patch.object(
            manifest_api, "_sum_external", wraps=manifest_api._sum_external
        ) as summed:
            one_year = manifest_api.load_forecast(manifest, 0, 0, cache)
            two_years = manifest_api.load_forecast(manifest, 0, 1, cache)
            manifest_api.write_rates(manifest, 0, str(cache / "rates.f32"), 1)
        self.assertEqual(summed.call_count, 1)

        self.assertAlmostEqual(one_year["total"], self.rates.sum())
        self.assertAlmostEqual(two_years["total"], 2 * self.rates.sum())
        self.assertEqual(two_years["rate_scale"], 2.0)
        np.testing.assert_allclose(
            two_years["magnitude_rates"], 2 * self.rates.sum(axis=0), 1e-3
        )
        cells = np.fromfile(cache / "rates.f32", dtype="<f4")
        np.testing.assert_allclose(cells, self.rates.sum(axis=1), rtol=1e-6)

    def test_changed_forecast_is_summed_again(self):
        cache = self.dir / "cache"
        path = self.dir / "a.npy"
        first, _ = manifest_api._external_sums(np.load(path), path, cache)
        np.save(path, 2 * self.rates[:-1])  # new size, so a new identity
        second, _ = manifest_api._external_sums(np.load(path), path, cache)
        np.testing.assert_allclose(second, 2 * self.rates[:-1].sum(axis=1))
        self.assertEqual(first.size, 12)

    def test_unreadable_saved_sums_are_computed_again(self):
        manifest = self.write_manifest()
        cache = self.dir / "cache"
        manifest_api.load_forecast(manifest, 0, 0, cache)
        (saved,) = cache.glob("sums-*.npz")
        for damage in (b"", saved.read_bytes()[:100]):  # empty, and a truncated zip
            with self.subTest(size=len(damage)):
                saved.write_bytes(damage)
                document = manifest_api.load_forecast(manifest, 0, 1, cache)
                self.assertAlmostEqual(document["total"], 2 * self.rates.sum())
                with np.load(saved) as sums:  # saved again, readable
                    np.testing.assert_allclose(sums["cells"], self.rates.sum(axis=1))

    def test_array_not_matching_its_declaration_is_an_error(self):
        manifest = self.write_manifest()
        for shape in ((10, 2), (12, 3), (12,)):
            with self.subTest(shape=shape):
                np.save(self.dir / "a.npy", np.ones(shape))
                with self.assertRaisesRegex(ValueError, "has shape"):
                    manifest_api.load_forecast(manifest, 0, 0, self.dir / "cache")
                with self.assertRaisesRegex(ValueError, "has shape"):
                    manifest_api.write_rates(manifest, 0, str(self.dir / "rates.f32"))


class TestForecastUnit(unittest.TestCase):
    def test_time_dependent_models_are_loaded_with_a_unit_of_one_year(self):
        # As floatCSEP: TimeDependentModel.get_forecast passes no forecast_unit
        self.assertIsNone(
            manifest_api._forecast_unit({"time_dependent": True, "forecast_unit": 5})
        )
        self.assertEqual(
            manifest_api._forecast_unit({"time_dependent": False, "forecast_unit": 5}), 5
        )
        self.assertEqual(
            manifest_api._forecast_unit({"forecast_unit": 5}), 5
        )  # older manifests


class TestVersions(unittest.TestCase):
    def test_cache_versions_agree(self):
        # Cached documents are keyed on the TypeScript version and written by the Python one
        source = Path(manifest_api.__file__).parent / "lib" / "server" / "python.ts"
        match = re.search(r"const DATA_VERSION = (\d+);", source.read_text())
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), manifest_api.FORMAT_VERSION)


class TestManifestFile(unittest.TestCase):
    def test_one_manifest_per_experiment(self):
        from floatcsep.postprocess.nextjs.server import manifest_file

        def manifest(root, config):
            return SimpleNamespace(app_root=root, config_file=config)

        a = manifest_file(Path("/c"), manifest("/exp/a", "config.yml"))
        self.assertEqual(a, manifest_file(Path("/c"), manifest("/exp/a", "config.yml")))
        self.assertNotEqual(a, manifest_file(Path("/c"), manifest("/exp/b", "config.yml")))
        self.assertEqual(a.parent, Path("/c"))


class TestWindowScale(unittest.TestCase):
    def test_matches_pycsep_and_floatcsep(self):
        # The dashboard computes the scale without importing pyCSEP (seconds per request)
        from csep.utils.time_utils import decimal_year
        from floatcsep.utils.helpers import str2timewindow

        for window in (
            "2014-01-01 to 2022-01-01",
            "2016-02-29 to 2016-03-01",
            "2016-11-14 00:00:00 to 2016-11-14 12:30:15.250000",
            "2019-12-31 23:59:59 to 2020-12-31 23:59:59",
        ):
            start, end = str2timewindow(window.replace(" to ", "_"))
            for unit in (None, 1, 2.5):
                with self.subTest(window=window, unit=unit):
                    expected = (decimal_year(end) - decimal_year(start)) / (unit or 1.0)
                    self.assertEqual(manifest_api._window_scale(window, unit), expected)


class TestDependencies(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        (self.dir / "package.json").write_text("{}")

    def tearDown(self):
        self.tmp.cleanup()

    def failing_install(self):
        error = subprocess.CalledProcessError(1, ["npm", "install"])
        return patch.object(runtime.subprocess, "run", side_effect=error)

    def test_failed_update_keeps_the_installed_packages(self):
        # E.g. offline, after an upgrade that adds the install stamp
        installed = self.dir / "node_modules" / "next"
        installed.mkdir(parents=True)
        (installed / "package.json").write_text("{}")
        with self.failing_install(), patch.object(runtime.logger, "warning") as warn:
            runtime.ensure_nextjs_dependencies(self.dir, ["npm"], {})
        warn.assert_called_once()
        self.assertFalse((self.dir / "node_modules" / runtime.INSTALL_STAMP).exists())

    def test_failed_first_install_raises(self):
        with self.failing_install(), self.assertRaises(RuntimeError):
            runtime.ensure_nextjs_dependencies(self.dir, ["npm"], {})


if __name__ == "__main__":
    unittest.main()
