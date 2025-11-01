import os
import threading
from collections import OrderedDict, defaultdict, deque
from time import perf_counter
from typing import Union, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from floatcsep.infrastructure.environments import DockerManager
import logging

log = logging.getLogger("floatLogger")


class Task:
    """
    Represents a unit of work to be executed later as part of a task graph.

    A Task wraps an object instance, a method, and its arguments to allow for deferred
    execution. This is useful in workflows where tasks need to be executed in a specific order,
    often dictated by dependencies on other tasks.

    For instance, can wrap a floatcsep.model.Model, its method 'create_forecast' and the
    argument 'time_window', which can be executed later with Task.call() when, for example,
    task dependencies (parent nodes) have been completed.

    Args:
            instance (object): The instance whose method will be executed later.
            method (str): The method of the instance that will be called.
            **kwargs: Arguments to pass to the method when it is invoked.

    """

    def __init__(self, instance: object, method: str, **kwargs):

        self.obj = instance
        self.method = method
        self.kwargs = kwargs
        self.store = None  # In-case the returned object by the call is required as output

    def sign_match(self, obj: Union[object, str] = None, meth: str = None, kw_arg: Any = None):
        """
        Checks whether the task matches a given function signature.

        This method is used to verify if a task belongs to a given object, method, or if it
        uses a specific keyword argument. Useful for identifying tasks in a graph based on
        partial matches of their attributes.

        Args:
            obj: The object instance or its name (str) to match against.
            meth: The method name to match against.
            kw_arg: A specific keyword argument value to match against in the task's arguments.

        Returns:
            bool: True if the task matches the provided signature, False otherwise.
        """

        if self.obj == obj or obj == getattr(self.obj, "name", None):
            if meth == self.method:
                if kw_arg in self.kwargs.values():
                    return True
        return False

    def __str__(self):
        """
        Returns a string representation of the task, including the instance name, method, and
        arguments. Useful for debugging purposes.

        Returns:
            str: A formatted string describing the task.
        """
        task_str = f"\tClass: {self.obj.__class__.__name__}\n"
        a = getattr(self.obj, "name", None)
        if a:
            task_str += f"\tName: {a}\n"
        task_str += f"\tMethod: {self.method}\n"
        for i, j in self.kwargs.items():
            try:
                if isinstance(j, list):
                    task_str += f"\t\t{i}: {[k.name for k in j]} \n"
                else:
                    task_str += f"\t\t{i}: {j.name} \n"
            except AttributeError:
                task_str += f"\t\t{i}: {j} \n"

        return task_str[:-2]

    def run(self):
        """
        Executes the task by calling the method on the object instance with the stored
        arguments. If the instance has a `store` attribute, it will use that instead of the
        instance itself. Once executed, the result is stored in the `store` attribute if any
        output is produced.

        Returns:
            The output of the method execution, or None if the method does not return anything.
        """

        if hasattr(self.obj, "store"):
            self.obj = self.obj.store
        output = getattr(self.obj, self.method)(**self.kwargs)

        return output


class TaskGraph:
    """
    Context manager of floatcsep workload distribution.

    A TaskGraph is responsible for adding tasks, managing dependencies between tasks, and
    executing  tasks in the correct order. Tasks in the graph can depend on one another, and
    the graph ensures that each task is run after all of its dependencies have been satisfied.
    Contains a `Task` dictionary whose dict_keys are the Task to be executed with dict_values
    as the Task's dependencies.

    """

    def __init__(self) -> None:
        """
        Initializes the TaskGraph with an empty task dictionary and task count.
        """
        self.tasks = OrderedDict()
        self._ntasks = 0
        self.name = "floatcsep.infrastructure.engine.TaskGraph"
        self.profiler = Profiler()

    @property
    def ntasks(self) -> int:
        """
        Returns the number of tasks currently in the graph.

        Returns:
            int: The total number of tasks in the graph.
        """
        return self._ntasks

    @ntasks.setter
    def ntasks(self, n):
        self._ntasks = n

    def add(self, task: Task):
        """
        Adds a new task to the task graph.

        The task is added to the dictionary of tasks with no dependencies by default.

        Args:
            task (Task): The task to be added to the graph.
        """
        self.tasks[task] = []
        self.ntasks += 1

    def add_dependency(
        self, task, dep_inst: Union[object, str] = None, dep_meth: str = None, dkw: Any = None
    ):
        """
        Adds a dependency to a task already within the graph.

        Searches for other tasks within the graph whose signature matches the provided
        object instance, method name, or keyword argument. Any matches are added as
        dependencies to the provided task.

        Args:
            task (Task): The task to which dependencies will be added.
            dep_inst: The object instance or name of the dependency.
            dep_meth: The method name of the dependency.
            dkw: A specific keyword argument value of the dependency.

        Returns:
            None
        """
        deps = []
        for i, other_tasks in enumerate(self.tasks.keys()):
            if other_tasks.sign_match(dep_inst, dep_meth, dkw):
                deps.append(other_tasks)
        self.tasks[task].extend(deps)

    def _build_dependency_maps(self):  #
        """Return indegree and dependents maps for current tasks."""
        indegree = {t: 0 for t in self.tasks}
        dependents = defaultdict(list)
        for t, deps in self.tasks.items():
            indegree[t] = len(deps)
            for d in deps:
                dependents[d].append(t)
        return indegree, dependents

    def _run_task(self, task):
        """Execute a single task and record its duration"""
        t0 = perf_counter()
        try:
            return task.run()
        finally:
            dt_ms = (perf_counter() - t0) * 1000.0
            self.profiler.record(task, dt_ms)

    def run(self):
        """
        Executes in sequential all tasks in the task graph according to the order set in
        Experiment.set_tasks().

        Iterates over each task in the graph and runs it after its dependencies have been
        resolved.

        Returns:
            None
        """

        log.info(f"[Engine] Running {self.ntasks} tasks.")
        try:
            self.profiler.begin(mode="sequential", ntasks=self.ntasks)
            for task, deps in self.tasks.items():
                log.debug(f"[Engine] Running task: \n{task}")
                self._run_task(task)
                log.debug(f"[Engine] Done")

        except KeyboardInterrupt:
            log.warning("[Engine] Keyboard Interrupt")
            try:
                DockerManager.kill_containers(label_key="model_timewindow")
            except Exception as e:
                log.error(f"[Engine] Cleanup failed: {e}")
            finally:
                log.warning("[Engine] Exiting after cleanup.")
                os._exit(130)
        finally:
            self.profiler.end()

    def run_parallel(self, max_workers: int):
        indegree, dependents = self._build_dependency_maps()
        ready = deque([t for t, deg in indegree.items() if deg == 0])

        log.info(
            f"[Engine] Running {self.ntasks} tasks in parallel (max_workers={max_workers})"
        )

        running = {}
        completed = 0

        def submit_task(executor, task):
            log.debug(f"[Engine] Submit \n{task}")
            fut = executor.submit(self._run_task, task)  # note: TaskGraph still executes tasks
            running[fut] = task

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            try:
                self.profiler.begin(
                    mode=f"parallel (max_workers={max_workers})", ntasks=self.ntasks
                )

                while ready and len(running) < max_workers:
                    submit_task(ex, ready.popleft())
                while running:
                    for fut in as_completed(list(running.keys()), timeout=None):
                        task = running.pop(fut)
                        try:
                            fut.result()
                            log.debug(f"[Engine] Done \n{task}")
                        except Exception as e:
                            log.error(f"[Engine] Fail \n{task}: {e}")
                        completed += 1

                        for dep in dependents[task]:
                            indegree[dep] -= 1
                            if indegree[dep] == 0:
                                ready.append(dep)
                        while ready and len(running) < max_workers:
                            submit_task(ex, ready.popleft())
            except KeyboardInterrupt:
                log.warning("[Engine] Keyboard Interrupt")
                try:
                    DockerManager.kill_containers(label_key="model_timewindow")
                except Exception as e:
                    log.error(f"[Engine] Cleanup failed: {e}")
                finally:
                    log.warning("[Engine] Exiting after cleanup.")
                    os._exit(130)
            finally:
                self.profiler.end()


class Profiler:
    """Collect per-task timings and emit one clean summary at session end."""

    def __init__(self):
        self._lock = threading.Lock()
        self._groups = {}
        self._t0 = 0.0
        self._mode = ""
        self._ntasks = 0

    def begin(self, mode: str, ntasks: int) -> None:
        self._mode = mode
        self._ntasks = ntasks
        self._groups.clear()
        self._t0 = perf_counter()

    def end(self) -> None:
        total_wall = perf_counter() - self._t0
        log.info(
            f"[Engine] Calculation in {self._mode} completed | Total time: {fmt_wall(total_wall)} | Tasks: {self._ntasks}"
        )

        if not self._groups or not log.isEnabledFor(logging.DEBUG):
            return

        items = sorted(self._groups.items(), key=lambda kv: kv[1]["ms"], reverse=True)
        total_ms = sum(v["ms"] for v in self._groups.values()) or 1.0

        def _fmt(ms: float) -> str:
            return f"{ms / 1000:.2f}s" if ms >= 1000 else f"{ms:.0f}ms"

        log.debug("[Engine] Breakdown by group:")
        log.debug("[Engine] Task: Share | N Tasks | Mean t | Max t | Total t")
        log.debug("[Engine] ------------------------------------------------")
        for name, stats in items:
            cnt = stats["count"]
            ms = stats["ms"]
            mx = stats.get("max_ms", 0.0)
            avg = (ms / cnt) if cnt else 0.0
            share = 100.0 * ms / total_ms
            log.debug(
                f"[Engine] {name}: {share:.0f}% | {cnt}x | {_fmt(avg)} | {_fmt(mx)} | {_fmt(ms)}"
            )

    def record(self, task, dt_ms: float) -> None:
        """Record a single task duration (in ms) under its group."""
        g = self.group_for(task)
        with self._lock:
            entry = self._groups.setdefault(g, {"count": 0, "ms": 0.0, "max_ms": 0.0})
            entry["count"] += 1
            entry["ms"] += dt_ms
            if dt_ms > entry["max_ms"]:
                entry["max_ms"] = dt_ms

    @staticmethod
    def group_for(task) -> str:
        """Map task.object type to the requested group name."""
        cls = getattr(task.obj, "__class__", type(task.obj)).__name__
        if cls == "CatalogRepository":
            return "Catalogs"
        if cls in ("Model", "TimeDependentModel", "TimeIndependentModel"):
            name = getattr(task.obj, "name", "Model")
            return f"Forecasts / {name}"  # one-line change for finer buckets
        if cls == "Evaluation":
            return "Evaluations"
        return "Other"


def fmt_wall(s: float) -> str:
    mins, secs = divmod(s, 60)
    hrs, mins = divmod(int(mins), 60)
    if hrs:
        return f"{hrs}h {mins}m {secs:.2f}s"
    if mins:
        return f"{mins}m {secs:.2f}s"
    return f"{secs:.2f}s"
