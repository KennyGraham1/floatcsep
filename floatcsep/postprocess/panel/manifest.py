import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from floatcsep.utils.helpers import timewindow2str


def _rel(path: Union[os.PathLike, str], base: Union[os.PathLike, str]) -> str:
    rel = os.path.relpath(str(path), str(base))
    return rel.replace("\\", "/")


@dataclass
class Manifest:
    name: str
    date_range: str
    magnitudes: List[float]
    region: Optional[str]
    models: List[str]
    tests: List[str]
    time_windows: List[str]
    catalog: Dict[str, str]
    forecasts: Dict[Tuple[str, str], str]
    results_main: Dict[Tuple[str, str], str]
    results_model: Dict[Tuple[str, str, str], str]
    app_root: str


def build_manifest(experiment: Any, app_root: Optional[str] = None) -> Manifest:
    reg = experiment.registry
    if app_root is None:
        app_root = reg.abs(reg.run_dir)

    name = getattr(experiment, "name", "Experiment")
    start = getattr(experiment, "start_date", "?")
    end = getattr(experiment, "end_date", "?")
    date_range = f"{start.date()} — {end.date()}"
    magnitudes = list(getattr(experiment, "magnitudes", []))
    region = getattr(experiment, "region", None)

    tw_all: List[str] = []
    for tw in getattr(experiment, "time_windows", []):
        tw_all.append(timewindow2str(tw))

    models: List[str] = [getattr(m, "name", str(m)) for m in getattr(experiment, "models", [])]
    tests: List[str] = [getattr(t, "name", str(t)) for t in getattr(experiment, "tests", [])]

    catalog: Dict[str, str] = {}
    try:
        cat_map = reg.get_figure_key("main_catalog_map") + ".png"
        cat_time = reg.get_figure_key("main_catalog_time") + ".png"
        catalog["map"] = _rel(cat_map, app_root)
        catalog["time"] = _rel(cat_time, app_root)
    except Exception:
        pass

    forecasts: Dict[Tuple[str, str], str] = {}
    for tw_str in tw_all:
        for model_name in models:
            try:
                p = reg.get_figure_key(tw_str, "forecasts", model_name)
                forecasts[(tw_str, model_name)] = _rel(p, app_root)
            except Exception:
                continue

    results_main: Dict[Tuple[str, str], str] = {}
    results_model: Dict[Tuple[str, str, str], str] = {}
    for tw_str in tw_all:
        for test_name in tests:
            try:
                p = reg.get_figure_key(tw_str, test_name)
                results_main[(tw_str, test_name)] = _rel(p, app_root)
            except Exception:
                pass
            for model_name in models:
                try:
                    p = reg.get_figure_key(tw_str, f"{test_name}_{model_name}")
                    results_model[(tw_str, test_name, model_name)] = _rel(p, app_root)
                except Exception:
                    continue

    return Manifest(
        name=name,
        date_range=date_range,
        magnitudes=magnitudes,
        region=region,
        models=models,
        tests=tests,
        time_windows=tw_all,
        catalog=catalog,
        forecasts=forecasts,
        results_main=results_main,
        results_model=results_model,
        app_root=str(app_root),
    )
