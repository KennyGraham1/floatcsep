import threading
import time
from collections import OrderedDict, defaultdict, deque
from time import perf_counter
from typing import Union, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

log = logging.getLogger()

def _fmt_secs(s: float) -> str:
    mins, secs = divmod(s, 60)
    hrs, mins = divmod(int(mins), 60)
    if hrs:
        return f"{hrs}h {mins}m {secs:.2f}s"
    if mins:
        return f"{mins}m {secs:.2f}s"
    return f"{secs:.2f}s"


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

        self.store = None  # Bool for nested tasks.

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
        task_str = f"{self.__class__}\n\t" f"Instance: {self.obj.__class__.__name__}\n"
        a = getattr(self.obj, "name", None)
        if a:
            task_str += f"\tName: {a}\n"
        task_str += f"\tMethod: {self.method}\n"
        for i, j in self.kwargs.items():
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

        if output:
            self.store = output
            del self.obj

        return output

    def __call__(self, *args, **kwargs):
        """
        A callable alias for the `run` method. Allows the task to be invoked directly.

        Returns:
            The result of the `run` method.
        """
        return self.run()


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
        self._prof = defaultdict(lambda: {"count": 0, "ms": 0.0})  #
        self._prof_lock = threading.Lock()  #

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

    def _bucket(self, task: "Task") -> str:
        m = task.method
        obj = task.obj
        if m == "set_test_cat":
            return "prep:set_test_cat"
        if m == "set_input_cat":
            return "prep:set_input_cat"
        if m == "create_forecast":
            return "model:create_forecast"
        if m == "get_forecast":
            return "eval:get_forecast"
        if m == "compute":
            t = getattr(obj, "type", None)
            return f"eval:compute:{t}" if t else "eval:compute"
        return f"other:{m}"

    def _accum(self, bucket: str, dur_ms: float) -> None:
        with self._prof_lock:
            s = self._prof[bucket]
            s["count"] += 1
            s["ms"] += dur_ms

    def _print_prof(self, total_s: float) -> None:
        items = sorted(self._prof.items(), key=lambda kv: kv[1]["ms"], reverse=True)
        from math import isfinite

        total_s = total_s if isfinite(total_s) else 0.0
        log.info(f"[TaskGraph] total_wall={total_s:.3f}s  tasks={self.ntasks}")
        for name, stats in items:
            cnt, ms = stats["count"], stats["ms"]
            avg = (ms / cnt) if cnt else 0.0
            log.info(
                f"[TaskGraph] {name:24s} count={cnt:3d} time={ms/1000:.3f}s avg={avg:.1f}ms"
            )

    def _build_dependency_maps(self):  #
        """Return indegree and dependents maps for current tasks."""
        indegree = {t: 0 for t in self.tasks}
        dependents = defaultdict(list)
        for t, deps in self.tasks.items():
            indegree[t] = len(deps)
            for d in deps:
                dependents[d].append(t)
        return indegree, dependents

    def run(self):
        """
        Executes all tasks in the task graph in the correct order based on dependencies.

        Iterates over each task in the graph and runs it after its dependencies have been
        resolved.

        Returns:
            None
        """

        log.info(f"[TaskGraph] Running {self.ntasks} tasks in serial")
        t0 = perf_counter()
        for task, deps in self.tasks.items():
            bucket = self._bucket(task) #
            s = time.perf_counter()
            log.debug(f"[TaskGraph] RUN (serial) {task}")
            task.run()
            e = time.perf_counter()
            self._accum(bucket, (e - s) * 1000.0)

        t1 = time.perf_counter()
        self._print_prof(total_s=(t1 - t0))
        # total = perf_counter() - t0
        # rate = (self.ntasks / total) if total > 0 else float("inf")
        # log.info(
        #     f"[TaskGraph] Serial execution complete in {_fmt_secs(total)} "
        #     f"({self.ntasks} tasks, {rate:.2f} tasks/s)"
        # )

    def run_parallel(self, max_workers: int):
        indegree, dependents = self._build_dependency_maps()
        ready = deque([t for t, deg in indegree.items() if deg == 0])

        log.info(
            f"[TaskGraph] Running {self.ntasks} tasks in parallel (max_workers={max_workers})"
        )

        t0 = perf_counter()
        running = {}
        completed = 0

        def submit_task(executor, task):
            log.debug(f"[TaskGraph] SUBMIT {task}")
            bucket = self._bucket(task)

            def _timed():
                s = perf_counter()
                try:
                    return task.run()
                finally:
                    e = perf_counter()
                    self._accum(bucket, (e - s) * 1000.0)

            fut = executor.submit(_timed)
            running[fut] = task

        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            # seed
            while ready and len(running) < max_workers:
                submit_task(ex, ready.popleft())

            while running:
                for fut in as_completed(list(running.keys()), timeout=None):
                    task = running.pop(fut)
                    try:
                        fut.result()
                        log.debug(f"[TaskGraph] DONE {task}")
                    except Exception as e:
                        log.error(f"[TaskGraph] FAIL {task}: {e}")
                    completed += 1

                    # release dependents
                    for dep in dependents[task]:
                        indegree[dep] -= 1
                        if indegree[dep] == 0:
                            ready.append(dep)

                    # backfill
                    while ready and len(running) < max_workers:
                        submit_task(ex, ready.popleft())

        total = perf_counter() - t0
        rate = (completed / total) if total > 0 else float("inf")
        log.info(
            f"[TaskGraph] Parallel execution complete in {_fmt_secs(total)} "
            f"({completed}/{self.ntasks} tasks, {rate:.2f} tasks/s)"
        )

        # <- NEW: print per-bucket summary
        self._print_prof(total_s=total)

    def __call__(self, *args, **kwargs):
        """
        A callable alias for the `run` method. Allows the task graph to be invoked directly.

        Returns:
            None
        """
        return self.run()
