import time
import unittest
import logging

from floatcsep.infrastructure.engine import TaskGraph, Task


class CatalogRepository:
    def __init__(self):
        self.name = "CatRepo"
        self.calls = []

    def set_test_cats(self, tstring):
        self.calls.append(("set_test_cats", tstring))
        time.sleep(0.01)
        return "ok"


class Model:
    def __init__(self, name="Dummy"):
        self.name = name
        self.calls = []

    def create_forecast(self, tstring, force=False):
        self.calls.append(("create_forecast", tstring, force))
        time.sleep(0.01)
        return "fc-ok"


class TestEngineModelIntegration(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger("floatLogger")
        self._old = self.logger.level
        self.logger.setLevel(logging.DEBUG)

    def tearDown(self):
        self.logger.setLevel(self._old)

    def test_serial_with_dependency(self):
        cat = CatalogRepository()
        mdl = Model("Dummy")

        g = TaskGraph()
        t_cat = Task(cat, "set_test_cats", tstring="W1")
        t_mdl = Task(mdl, "create_forecast", tstring="W1", force=False)

        g.add(t_cat)
        g.add(t_mdl)
        g.add_dependency(t_mdl, dep_inst=cat, dep_meth="set_test_cats", dkw="W1")

        g.run()

        self.assertIn(("set_test_cats", "W1"), cat.calls)
        self.assertIn(("create_forecast", "W1", False), mdl.calls)

    def test_parallel_dependency_and_profiler_groups(self):
        cat = CatalogRepository()
        mdl = Model("STEP")

        g = TaskGraph()
        t_cat = Task(cat, "set_test_cats", tstring="W2")
        t_mdl = Task(mdl, "create_forecast", tstring="W2", force=True)

        g.add(t_cat)
        g.add(t_mdl)
        g.add_dependency(t_mdl, dep_inst=cat, dep_meth="set_test_cats", dkw="W2")

        g.run_parallel(max_workers=2)

        self.assertIn(("set_test_cats", "W2"), cat.calls)
        self.assertIn(("create_forecast", "W2", True), mdl.calls)
