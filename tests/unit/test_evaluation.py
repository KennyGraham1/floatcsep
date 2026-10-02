import unittest
from unittest.mock import patch

import numpy
from csep.core.catalogs import CSEPCatalog
from csep.core.regions import CartesianGrid2D, QuadtreeGrid2D

from floatcsep.evaluation import Evaluation, filter_to_region, inside_quadtree


class TestEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        def mock_eval():
            return

        setattr(cls, "mock_eval", mock_eval)

    @staticmethod
    def init_noreg(name, func, **kwargs):
        evaluation = Evaluation(name=name, func=func, **kwargs)
        return evaluation

    def test_init(self):
        name = "N_test"
        eval_ = self.init_noreg(name=name, func=self.mock_eval)
        self.assertIs(None, eval_.type)
        dict_ = {
            "name": "N_test",
            "func": self.mock_eval,
            "func_kwargs": {},
            "ref_model": None,
            "plot_func": None,
            "plot_args": None,
            "plot_kwargs": None,
            "plot_modes": [],
            "markdown": "",
            "_type": None,
            "results_repo": None,
            "catalog_repo": None,
            "strict_region": True,
        }
        self.assertEqual(dict_, eval_.__dict__)

    def test_discrete_args(self):
        pass

    def test_sequential_args(self):
        pass

    def test_write_result(self):
        pass

    def to_dict(self):
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        pass


class TestFilterToRegion(unittest.TestCase):
    @staticmethod
    def catalog(lonlat):
        return CSEPCatalog(
            data=[(str(i), 0, lat, lon, 10.0, 6.0) for i, (lon, lat) in enumerate(lonlat)]
        )

    def test_quadtree(self):
        # "0": lon [-180, 0], lat [0, 85.05]; "10" and "11": lat [66.5, 85.05]
        region = QuadtreeGrid2D.from_quadkeys(["0", "10", "11"], magnitudes=numpy.array([5.0]))
        catalog = self.catalog([(-90, 45), (45, 45), (170, 80), (-90, -45)])
        filtered = filter_to_region(catalog, region)
        self.assertIs(filtered, catalog)
        self.assertIs(filtered.region, region)
        numpy.testing.assert_array_equal(filtered.get_longitudes(), [-90, 170])
        numpy.testing.assert_array_equal(filtered.get_latitudes(), [45, 80])

    def assert_matches_every_cell(self, region, lons, lats):
        """inside_quadtree, both by tile lookup and by testing all cells, against pyCSEP's
        test of every cell's bounds, one point at a time."""
        bounds = numpy.asarray(region.bounds)
        west, south, east, north = bounds.T
        expected = numpy.array(
            [
                numpy.any((west <= lon) & (lon < east) & (south <= lat) & (lat < north))
                for lon, lat in zip(lons, lats)
            ]
        )
        with patch("floatcsep.evaluation._BRUTE_FORCE_PAIRS", 0):  # the tile lookup
            numpy.testing.assert_array_equal(inside_quadtree(region, lons, lats), expected)
        with patch("floatcsep.evaluation._BRUTE_FORCE_PAIRS", 10**12):  # all cells at once
            numpy.testing.assert_array_equal(inside_quadtree(region, lons, lats), expected)
        self.assertTrue(expected.any() and not expected.all())

    def test_quadtree_matches_testing_every_cell(self):
        # Also for points on cell edges (both lon and lat), beyond the Mercator latitudes,
        # and outside a grid that covers part of the globe only.
        rng = numpy.random.default_rng(7)
        seeds = CSEPCatalog(
            data=[
                (str(i), 0, lat, lon, 10.0, 6.0)
                for i, (lon, lat) in enumerate(
                    zip(rng.normal(140, 15, 400), numpy.clip(rng.normal(35, 12, 400), -80, 80))
                )
            ]
        )
        full = QuadtreeGrid2D.from_catalog(seeds, threshold=5, zoom=9)
        partial = QuadtreeGrid2D.from_quadkeys(
            [str(q) for q in full.quadkeys if str(q).startswith(("12", "30"))]
        )
        for region in (full, partial):
            bounds = numpy.asarray(region.bounds)
            lons = numpy.concatenate(
                [
                    rng.uniform(-180, 180, 3000),
                    bounds[:, 0],  # west edges
                    bounds[:, 0],
                    rng.uniform(-180, 180, 50),
                    [0.0, 180.0, -180.0, 45.0, 170.0],
                ]
            )
            lats = numpy.concatenate(
                [
                    rng.uniform(-89, 89, 3000),
                    bounds[:, 1],  # south edges
                    bounds[:, 3],  # north edges
                    rng.choice([85.0511287798, 85.06, -85.06, 89.9], 50),
                    [0.0, 10.0, 10.0, 0.0, 90.0],
                ]
            )
            self.assert_matches_every_cell(region, lons, lats)

    def test_quadtree_high_zoom_edges(self):
        # At zoom 20 and beyond, the computed tile of a point on an edge can be off by one,
        # most at high latitudes: the neighbouring tiles must be tested too.
        import mercantile

        rng = numpy.random.default_rng(11)
        for zoom in (20, 22, 24):
            keys = set()
            for lat in (0.3, 45.2, 72.5, 84.9):
                for lon in (-179.9, 10.3, 142.4):
                    tile = mercantile.tile(lon, lat, zoom)
                    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
                        keys.add(mercantile.quadkey(tile.x + dx, tile.y + dy, zoom))
            region = QuadtreeGrid2D.from_quadkeys(sorted(keys))
            bounds = numpy.asarray(region.bounds)
            span = bounds[:, 2:] - bounds[:, :2]
            lons = numpy.concatenate(
                [bounds[:, 0], bounds[:, 0], bounds[:, 2], bounds[:, 0] + span[:, 0] / 2]
                + [bounds[:, 0] + span[:, 0] * rng.uniform(-1, 2, len(bounds))]
            )
            lats = numpy.concatenate(
                [bounds[:, 1], bounds[:, 3], bounds[:, 1], bounds[:, 3]]
                + [bounds[:, 1] + span[:, 1] * rng.uniform(-1, 2, len(bounds))]
            )
            with self.subTest(zoom=zoom):
                self.assert_matches_every_cell(region, lons, lats)

    def test_quadtree_empty_catalog(self):
        region = QuadtreeGrid2D.from_quadkeys(["0"], magnitudes=numpy.array([5.0]))
        filtered = filter_to_region(CSEPCatalog(data=[]), region)
        self.assertEqual(filtered.event_count, 0)

    def test_cartesian(self):
        # Regular grids keep pyCSEP's own spatial filter: cells of lon [0, 2], lat [0, 2].
        origins = numpy.array([[0.0, 0.0], [1.0, 0.0], [0.0, 1.0], [1.0, 1.0]])
        region = CartesianGrid2D.from_origins(origins, dh=1.0, magnitudes=numpy.array([5.0]))
        catalog = self.catalog([(0.5, 0.5), (1.5, 1.5), (2.5, 0.5), (0.5, 2.5), (-0.5, 0.5)])
        filtered = filter_to_region(catalog, region)
        numpy.testing.assert_array_equal(filtered.get_longitudes(), [0.5, 1.5])
        numpy.testing.assert_array_equal(filtered.get_latitudes(), [0.5, 1.5])
