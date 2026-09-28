import unittest

import numpy
from csep.core.catalogs import CSEPCatalog
from csep.core.regions import CartesianGrid2D, QuadtreeGrid2D

from floatcsep.evaluation import Evaluation, filter_to_region


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
