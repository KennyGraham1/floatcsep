import logging
import unittest
import time
from unittest.mock import patch
from floatcsep.infrastructure.engine import Task, TaskGraph, fmt_wall


class Dummy:
    def __init__(self, name):
        self.name = name

    def dummy_method(self, x):
        return x


class TestTask(unittest.TestCase):

    def setUp(self):
        self.obj = Dummy("TestObj")
        self.task = Task(instance=self.obj, method="dummy_method", x=10)

    def test_init(self):
        self.assertEqual(self.task.obj, self.obj)
        self.assertEqual(self.task.method, "dummy_method")
        self.assertEqual(getattr(self.obj, self.task.method)(10), 10)

    def test_sign_match(self):
        self.assertTrue(self.task.sign_match(obj=self.obj, meth="dummy_method", kw_arg=10))
        self.assertFalse(
            self.task.sign_match(obj="NonMatching", meth="dummy_method", kw_arg=10)
        )

    def test___str__(self):
        task_str = str(self.task)
        self.assertIn("TestObj", task_str)
        self.assertIn("dummy_method", task_str)
        self.assertIn("10", task_str)

    def test_run(
        self,
    ):
        result = self.task.run()
        self.assertEqual(result, 10)


class TestTaskEdges(unittest.TestCase):
    def test_str_with_list_kwargs(self):
        d = Dummy("D")
        other = Dummy("O1"), Dummy("O2")
        t = Task(instance=d, method="dummy_method", items=list(other), value=5)
        s = str(t)
        self.assertIn("D", s)
        self.assertIn("items", s)
        self.assertIn("O1", s)
        self.assertIn("O2", s)
        self.assertIn("value", s)

    def test_sign_match_by_name(self):
        d = Dummy("MatchMe")
        t = Task(instance=d, method="dummy_method", x=7)
        self.assertTrue(t.sign_match(obj="MatchMe", meth="dummy_method", kw_arg=7))
        self.assertFalse(t.sign_match(obj="Nope", meth="dummy_method", kw_arg=7))


class TestTaskGraph(unittest.TestCase):

    def setUp(self):
        self.graph = TaskGraph()
        self.obj = Dummy("TestObj")
        self.task_a = Task(instance=self.obj, method="dummy_method", x=10)
        self.task_b = Task(instance=self.obj, method="dummy_method", x=20)

    def test_init(self):
        self.assertEqual(self.graph.ntasks, 0)
        self.assertEqual(self.graph.name, "floatcsep.infrastructure.engine.TaskGraph")

    def test_add(self):
        self.graph.add(self.task_a)
        self.assertIn(self.task_a, self.graph.tasks)
        self.assertEqual(self.graph.ntasks, 1)

    def test_add_dependency(self):
        self.graph.add(self.task_a)
        self.graph.add(self.task_b)
        self.graph.add_dependency(
            self.task_b, dep_inst=self.obj, dep_meth="dummy_method", dkw=10
        )
        self.assertIn(self.task_a, self.graph.tasks[self.task_b])

    def test_run(self):
        self.graph.add(self.task_a)
        self.graph.run()


class Sleeper:
    def __init__(self, name):
        self.name = name

    def sleep(self, secs):
        time.sleep(secs)
        return secs


class TestGraphParallel(unittest.TestCase):
    def test_parallel_concurrency(self):
        g = TaskGraph()
        s = Sleeper("S")
        for _ in range(6):
            g.add(Task(s, "sleep", secs=0.2))

        t0 = time.perf_counter()
        g.run_parallel(max_workers=6)
        dt = time.perf_counter() - t0

        self.assertLess(dt, 0.8)


class KO:
    def __init__(self, name):
        self.name = name

    def boom(self):
        raise KeyboardInterrupt


class TestInterrupt(unittest.TestCase):
    @patch("floatcsep.infrastructure.engine.os._exit")
    @patch("floatcsep.infrastructure.engine.DockerManager.kill_containers")
    def test_keyboard_interrupt_triggers_cleanup(self, mock_kill, mock_exit):
        g = TaskGraph()
        k = KO("K")
        g.add(Task(k, "boom"))
        g.run()

        mock_kill.assert_called_once_with(label_key="model_timewindow")
        mock_exit.assert_called_once()
        self.assertEqual(mock_exit.call_args[0][0], 130)


class TestDependencies(unittest.TestCase):
    def test_add_dependency_wires(self):
        g = TaskGraph()
        d = Dummy("D")
        a = Task(d, "f", x=1)
        b = Task(d, "f", x=2)
        g.add(a)
        g.add(b)
        g.add_dependency(b, dep_inst=d, dep_meth="f", dkw=1)
        indegree, dependents = g._build_dependency_maps()
        self.assertIn(b, dependents[a])
        self.assertEqual(indegree[a], 0)
        self.assertEqual(indegree[b], 1)


class Boom:
    def __init__(self, name):
        self.name = name

    def fail(self):
        raise RuntimeError("boom")


class DepObj:
    def __init__(self, name):
        self.name = name

    def ok(self):
        return "ok"


class KIBoom:
    def __init__(self, name):
        self.name = name

    def ki(self):
        raise KeyboardInterrupt


class TestParallelExceptionPath(unittest.TestCase):
    def test_parallel_logs_exception_and_continues(self):
        g = TaskGraph()
        good = DepObj("Good")
        bad = Boom("Bad")
        g.add(Task(bad, "fail"))
        g.add(Task(good, "ok"))
        g.run_parallel(max_workers=2)


class TestParallelDependencyRelease(unittest.TestCase):
    def test_dependency_release_and_backfill_submit(self):
        g = TaskGraph()
        obj = DepObj("Dep")

        a = Task(obj, "ok")
        b = Task(obj, "ok")
        g.add(a)
        g.add(b)
        g.add_dependency(b, dep_inst=obj, dep_meth="ok", dkw=None)
        g.run_parallel(max_workers=1)


class TestParallelKeyboardInterrupt(unittest.TestCase):
    @patch("floatcsep.infrastructure.engine.os._exit")
    @patch("floatcsep.infrastructure.engine.DockerManager.kill_containers")
    def test_keyboard_interrupt_triggers_cleanup_parallel(self, mock_kill, mock_exit):
        g = TaskGraph()
        ki = KIBoom("KI")
        g.add(Task(ki, "ki"))

        g.run_parallel(max_workers=1)

        mock_kill.assert_called_once_with(label_key="model_timewindow")
        mock_exit.assert_called_once()
        self.assertEqual(mock_exit.call_args[0][0], 130)


class CatalogRepository:
    def __init__(self):
        self.name = "CatRepo"

    def t(self):
        time.sleep(0.01)


class Model:
    def __init__(self, name):
        self.name = name

    def t(self):
        time.sleep(0.01)


class Evaluation:
    def __init__(self):
        self.name = "Eval"

    def t(self):
        time.sleep(0.01)


class TestProfilerDebugBreakdown(unittest.TestCase):
    def test_profiler_debug_breakdown_emits(self):
        logger = logging.getLogger("floatLogger")
        old = logger.level
        logger.setLevel(logging.DEBUG)
        try:
            g = TaskGraph()
            g.add(Task(CatalogRepository(), "t"))
            g.add(Task(Model("STEP"), "t"))
            g.add(Task(Evaluation(), "t"))
            g.run()

        finally:
            logger.setLevel(old)


class Weird:
    def __init__(self):
        self.name = "Weird"

    def t(self):
        return 42


class TestGroupForOther(unittest.TestCase):
    def test_group_for_other_branch(self):
        g = TaskGraph()
        g.profiler.begin("Serial", 1)
        g._run_task(Task(Weird(), "t"))
        g.profiler.end()


class TestFmtWall(unittest.TestCase):
    def test_fmt_wall_seconds(self):
        self.assertIn("5.00s", fmt_wall(5.0))

    def test_fmt_wall_minutes(self):
        self.assertIn("1m", fmt_wall(75.0))

    def test_fmt_wall_hours(self):
        self.assertIn("1h", fmt_wall(3700.0))


if __name__ == "__main__":
    unittest.main()
