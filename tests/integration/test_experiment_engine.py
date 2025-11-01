import unittest
from unittest.mock import patch, MagicMock
from floatcsep.experiment import Experiment


class FakeTaskGraph:
    def __init__(self):
        self.ran_serial = False
        self.ran_parallel = False
        self._ntasks = 3

    @property
    def ntasks(self):
        return self._ntasks

    def run(self):
        self.ran_serial = True

    def run_parallel(self, max_workers: int):
        self.ran_parallel = True
        self.max_workers = max_workers


class TestExperimentEngineInterface(unittest.TestCase):
    def make_minimal_experiment(self):
        exp = Experiment.__new__(Experiment)
        exp.task_graph = FakeTaskGraph()
        exp.run_mode = "serial"
        exp.seed = None
        exp.concurrent_tasks = None
        exp.time_windows = []
        exp.registry = MagicMock()
        exp.models = []
        exp.tests = []

        return exp

    @patch("floatcsep.experiment.log_results_tree")
    @patch("floatcsep.experiment.log_models_tree")
    def test_serial_dispatch(self, _lm, _lr):
        exp = self.make_minimal_experiment()
        exp.run()
        self.assertTrue(exp.task_graph.ran_serial)
        self.assertFalse(exp.task_graph.ran_parallel)

    @patch("floatcsep.experiment.numpy.random.seed")
    @patch("floatcsep.experiment.log_results_tree")
    @patch("floatcsep.experiment.log_models_tree")
    def test_seed_and_parallel_dispatch(self, _lm, _lr, mock_seed):
        exp = self.make_minimal_experiment()
        exp.run_mode = "parallel"
        exp.concurrent_tasks = 5
        exp.seed = 1234

        exp.run()

        mock_seed.assert_called_once_with(1234)
        self.assertTrue(exp.task_graph.ran_parallel)
        self.assertEqual(exp.task_graph.max_workers, 5)

    @patch("floatcsep.experiment.log_results_tree")
    @patch("floatcsep.experiment.log_models_tree")
    def test_parallel_fallback_to_cpu_count(self, _lm, _lr):
        exp = self.make_minimal_experiment()
        exp.run_mode = "parallel"
        with patch("floatcsep.experiment.os.cpu_count", return_value=7):
            exp.run()
        self.assertTrue(exp.task_graph.ran_parallel)
        self.assertEqual(exp.task_graph.max_workers, 7)
