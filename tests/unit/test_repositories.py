import datetime
import os
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch, PropertyMock, mock_open

from csep.core.catalogs import CSEPCatalog
from csep.core.forecasts import GriddedForecast
from csep.utils.time_utils import datetime_to_utc_epoch

from floatcsep.utils.file_io import CatalogParser, GriddedForecastParsers
from floatcsep.infrastructure.registries import ModelFileRegistry
from floatcsep.infrastructure.repositories import (
    CatalogForecastRepository,
    GriddedForecastRepository,
    ResultsRepository,
    CatalogRepository,
)


class TestCatalogForecastRepository(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock(spec=ModelFileRegistry)  # todo: Factory registry
        self.registry.__call__ = MagicMock(return_value="a_duck")
        self.registry.fmt = "csv"

    @patch("csep.load_catalog_forecast")
    def test_initialization(self, mock_load_catalog_forecast):
        repo = CatalogForecastRepository(self.registry, lazy_load=True)
        self.assertTrue(repo.lazy_load)

    @patch("floatcsep.file_io.CatalogForecastParsers.csv")
    def test_load_forecast(self, mock_load_catalog_forecast):
        repo = CatalogForecastRepository(self.registry)

        mock_load_catalog_forecast.return_value = "forecatto"
        forecast = repo.load_forecast("2023-01-01_2023-01-02")
        self.assertEqual(forecast, "forecatto")

        # Test load_forecast with list
        forecasts = repo.load_forecast(["2023-01-01_2023-01-01", "2023-01-02_2023-01-03"])
        self.assertEqual(forecasts, ["forecatto", "forecatto"])

    @patch("floatcsep.file_io.CatalogForecastParsers.csv")
    def test_load_single_forecast(self, mock_load_catalog_forecast):
        # Test _load_single_forecast
        repo = CatalogForecastRepository(self.registry)
        mock_load_catalog_forecast.return_value = "forecatto"
        forecast = repo._load_single_forecast("2023-01-01_2023-01-01")
        self.assertEqual(forecast, "forecatto")


class TestGriddedForecastRepository(unittest.TestCase):

    def setUp(self):
        self.registry = MagicMock(spec=ModelFileRegistry)  # todo: Factory registry
        self.registry.fmt = "hdf5"
        self.registry.__call__ = MagicMock(return_value="a_duck")

    def test_initialization(self):
        repo = GriddedForecastRepository(self.registry, lazy_load=False)
        self.assertFalse(repo.lazy_load)

    @patch.object(GriddedForecastParsers, "hdf5")
    def test_load_forecast(self, mock_parser):
        # Mock parser return values
        mock_parser.return_value = ("rates", "region", "mags")

        repo = GriddedForecastRepository(self.registry)
        with patch.object(
            repo, "_get_or_load_forecast", return_value="forecatto"
        ) as mock_method:
            forecast = repo.load_forecast("2023-01-01_2023-01-02")
            self.assertEqual(forecast, "forecatto")
            mock_method.assert_called_once_with("2023-01-01_2023-01-02", "", 1)

        # Test load_forecast with list
        with patch.object(
            repo, "_get_or_load_forecast", return_value="forecatto"
        ) as mock_method:
            forecasts = repo.load_forecast(["2023-01-01_2023-01-02", "2023-01-02_2023-01-03"])
            self.assertEqual(forecasts, ["forecatto", "forecatto"])
            self.assertEqual(mock_method.call_count, 2)

    @patch.object(GriddedForecastParsers, "hdf5")
    def test_get_or_load_forecast(self, mock_parser):
        mock_parser.return_value = ("rates", "region", "mags")
        repo = GriddedForecastRepository(self.registry, lazy_load=False)
        with patch.object(
            repo, "_load_single_forecast", return_value="forecatta"
        ) as mock_method:
            # Test when forecast is not in memory
            forecast = repo._get_or_load_forecast("2023-01-01_2023-01-02", "test_name", 1)
            self.assertEqual(forecast, "forecatta")
            mock_method.assert_called_once_with("2023-01-01_2023-01-02", 1, "test_name")
            self.assertIn("2023-01-01_2023-01-02", repo.forecasts)

            # Test when forecast is in memory
            forecast = repo._get_or_load_forecast("2023-01-01_2023-01-02", "test_name", 1)
            self.assertEqual(forecast, "forecatta")
            mock_method.assert_called_once()  # Should not be called again

    @patch.object(GriddedForecast, "__init__", return_value=None)
    @patch.object(GriddedForecast, "event_count", new_callable=PropertyMock)
    @patch.object(GriddedForecast, "scale")
    @patch.object(GriddedForecastParsers, "hdf5")
    def test_load_single_forecast(self, mock_parser, mock_scale, mock_count, mock_init):
        # Mock parser return values
        mock_count.return_value = 2
        mock_parser.return_value = ("rates", "region", "mags")
        mock_scale.return_value = mock_scale

        # Test _load_single_forecast
        repo = GriddedForecastRepository(self.registry, lazy_load=False)
        with patch("csep.utils.time_utils.decimal_year", side_effect=[2023.0, 2024.0]):
            forecast = repo._load_single_forecast("2023-01-01_2024-01-01", 1, "axe")
            self.assertIsInstance(forecast, GriddedForecast)
            mock_init.assert_called_once_with(
                name="axe",
                data="rates",
                region="region",
                magnitudes="mags",
                start_time=datetime.datetime(2023, 1, 1),
                end_time=datetime.datetime(2024, 1, 1),
            )

    @patch.object(GriddedForecastParsers, "hdf5")
    def test_lazy_load_behavior(self, mock_parser):
        mock_parser.return_value = ("rates", "region", "mags")
        # Test lazy_load behavior
        repo = GriddedForecastRepository(self.registry, lazy_load=False)
        with patch.object(
            repo, "_load_single_forecast", return_value="forecatto"
        ) as mock_method:
            # Load forecast and check if it is stored
            forecast = repo.load_forecast("2023-01-01_2023-01-02")
            self.assertEqual(forecast, "forecatto")
            self.assertIn("2023-01-01_2023-01-02", repo.forecasts)

            # Change to lazy_load=True and check if forecast is not stored
            repo.lazy_load = True
            forecast = repo.load_forecast("2023-01-02_2023-01-03")
            self.assertEqual(forecast, "forecatto")
            self.assertNotIn("2023-01-02_2023-01-03", repo.forecasts)

    @patch("floatcsep.infrastructure.registries.ModelFileRegistry")
    def test_equal(self, MockModelFileRegistry):

        self.registry = MockModelFileRegistry()

        self.repo1 = CatalogForecastRepository(self.registry)
        self.repo2 = CatalogForecastRepository(self.registry)
        self.repo3 = CatalogForecastRepository(self.registry)
        self.repo4 = CatalogForecastRepository(self.registry)

        self.repo1.forecasts = {"1": 1, "2": 2}
        self.repo2.forecasts = {"1": 1, "2": 2}
        self.repo3.forecasts = {"1": 2, "2": 2}
        self.repo4.forecasts = {"3": 1, "2": 2}

        self.assertEqual(self.repo1, self.repo2)
        self.assertNotEqual(self.repo1, self.repo3)
        self.assertNotEqual(self.repo1, self.repo3)


class TestResultsRepository(unittest.TestCase):

    @patch("floatcsep.infrastructure.repositories.ExperimentRegistry.factory")
    def setUp(self, mock_registry):
        self.mock_registry = MagicMock()
        self.mock_registry.return_value = mock_registry()
        self.results_repo = ResultsRepository(self.mock_registry)

    def test_initialization(self):
        self.assertEqual(self.results_repo.registry, self.mock_registry)

    @patch("floatcsep.infrastructure.repositories.EvaluationResult.from_dict")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='{"key": "value"}')
    def test_load_result(self, mock_open, mock_from_dict):
        mock_from_dict.return_value = "mocked_result"
        result = self.results_repo._load_result("test", "window", "model")
        self.assertEqual(result, "mocked_result")

    @patch.object(ResultsRepository, "_load_result", return_value="mocked_result")
    def test_load_results(self, mock_load_result):
        results = self.results_repo.load_results("test", "window", ["model1", "model2"])
        self.assertEqual(results, ["mocked_result", "mocked_result"])

    @patch("json.dump")
    @patch("builtins.open", new_callable=unittest.mock.mock_open)
    def test_write_result(self, mock_open, mock_json_dump):
        mock_result = MagicMock()
        self.results_repo.write_result(mock_result, "test", "model", "window")
        mock_open.assert_called_once()
        mock_json_dump.assert_called_once()


class TestCatalogRepository(unittest.TestCase):

    @patch("floatcsep.infrastructure.repositories.ExperimentRegistry.factory")
    def setUp(self, mock_registry):
        self.mock_registry = MagicMock()
        self.mock_registry.return_value = mock_registry()
        self.catalog_repo = CatalogRepository(self.mock_registry)

    def test_initialization(self):
        self.assertEqual(self.catalog_repo.registry, self.mock_registry)

    @patch("floatcsep.infrastructure.repositories.isfile", return_value=True)
    @patch("csep.load_catalog", return_value="csep catalog")
    def test_set_catalog(self, mock_reader, mock_isfile):
        self.mock_registry.rel.return_value = "catalog_path"

        self.catalog_repo.set_main_catalog("catalog_path", {}, {})

        self.assertEqual(self.catalog_repo.cat_path, "catalog_path")
        self.assertEqual(self.catalog_repo._catalog, "csep catalog")


class TestCatalogWindowsAreUtc(unittest.TestCase):
    """Time windows are UTC, as catalog origin times, whatever the computer's time zone."""

    # Around the UTC day 2016-11-13 (New Zealand is 13 hours ahead in November)
    TIMES = {
        "a": datetime.datetime(2016, 11, 12, 20, 0),  # the day before (2016-11-13 in New Zealand)
        "b": datetime.datetime(2016, 11, 13, 5, 0),
        "c": datetime.datetime(2016, 11, 13, 11, 2),  # 2016-11-14 in New Zealand
        "d": datetime.datetime(2016, 11, 13, 23, 59),
        "e": datetime.datetime(2016, 11, 14, 0, 0),  # the next day: the window's end is excluded
    }

    def setUp(self):
        if not hasattr(time, "tzset"):
            self.skipTest("time zones cannot be changed on this platform")
        self.tz = os.environ.get("TZ")
        os.environ["TZ"] = "Pacific/Auckland"
        time.tzset()
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = CatalogRepository(MagicMock())
        self.repo.region_config = {"mag_min": 3.0, "mag_max": 8.0, "region": None}
        self.repo._catalog = CSEPCatalog(
            data=[
                (name, datetime_to_utc_epoch(t), -42.0, 173.0, 10.0, 5.0)
                for name, t in self.TIMES.items()
            ]
        )

    def tearDown(self):
        self.tmp.cleanup()
        if self.tz is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = self.tz
        time.tzset()

    def events(self, path, fmt="json"):
        return sorted(getattr(CatalogParser, fmt)(path).get_event_ids().astype(str))

    def test_test_catalog(self):
        path = os.path.join(self.tmp.name, "test.json")
        self.repo.registry.get_test_catalog_key.return_value = path
        self.repo.set_test_cats("2016-11-13_2016-11-14")
        self.assertEqual(self.events(path), ["b", "c", "d"])

    def test_input_catalog(self):
        # The events before the window, as a time-dependent model is given them
        path = os.path.join(self.tmp.name, "input.json")
        model = MagicMock()
        model.registry.get_input_catalog_key.return_value = path
        self.repo.set_input_cats("2016-11-13_2016-11-14", [model])
        self.assertEqual(self.events(path, "ascii"), ["a"])


if __name__ == "__main__":
    unittest.main()
