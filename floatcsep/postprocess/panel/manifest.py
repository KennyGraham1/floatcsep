import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from floatcsep.utils.helpers import timewindow2str

import datetime


def _rel(path: Union[os.PathLike, str], base: Union[os.PathLike, str]) -> str:
    rel = os.path.relpath(str(path), str(base))
    return rel.replace("\\", "/")


@dataclass
class Manifest:
    # --- Existing fields used by the layout ---
    name: str
    start_date: str
    end_date: str
    authors: str
    doi: str
    journal: str
    manuscript_doi: str
    exp_time: str
    floatcsep_version: str
    pycsep_version: str
    last_run: str
    catalog_doi: str
    license: str
    date_range: str
    magnitudes: List[float]
    region: Optional[Any]  # Region object (e.g. CartesianGrid2D)
    models: List[Dict[str, Any]]
    tests: List[Dict[str, Any]]
    time_windows: List[str]

    catalog: Dict[str, str]
    results_main: Dict[Tuple[str, str], str]
    results_model: Dict[Tuple[str, str, str], str]
    app_root: str

    # --- New metadata fields for the Experiment view / meta bar ---
    exp_class: str  # "Time-Independent" / "Time-Dependent"
    n_intervals: int  # number of time windows / intervals
    horizon: Optional[str]  # human-readable horizon (e.g. "1 year")
    offset: Optional[str]  # human-readable offset
    growth: Optional[str]  # "incremental" / "cumulative" / None

    mag_min: Optional[float]
    mag_max: Optional[float]
    mag_bin: Optional[float]
    depth_min: Optional[float]
    depth_max: Optional[float]

    run_mode: Optional[str]  # "sequential" / "parallel"
    run_dir: Optional[str]  # results directory (relative or abs)
    config_file: Optional[str]  # main config file path
    model_config: Optional[str]  # models config path
    test_config: Optional[str]  # tests config path


def _timedelta_to_str(value: Any) -> Optional[str]:
    """Best-effort pretty-print for horizon/offset."""
    if value is None:
        return None
    # If it's already a string, just return it
    if isinstance(value, str):
        return value
    # Timedelta-like: try to derive something nice
    try:
        days = value.days
        seconds = value.seconds
    except Exception:
        return str(value)

    if days and not seconds:
        # Use years if divisible by 365
        if days % 365 == 0:
            years = days // 365
            return f"{years} year{'s' if years != 1 else ''}"
        return f"{days} day{'s' if days != 1 else ''}"
    if not days and seconds:
        hours = seconds // 3600
        if hours:
            return f"{hours} hour{'s' if hours != 1 else ''}"
    # Fallback
    return str(value)


def build_manifest(experiment: Any, app_root: Optional[str] = None) -> Manifest:
    reg = experiment.registry
    cat_repo = experiment.catalog_repo
    if app_root is None:
        app_root = reg.abs(reg.run_dir)

    name = getattr(experiment, "name", "Experiment")
    start = getattr(experiment, "start_date", None)
    end = getattr(experiment, "end_date", None)
    authors = getattr(experiment, "authors", None)
    doi = getattr(experiment, "doi", None)
    catalog_doi = getattr(experiment, "catalog_doi", None)
    license_ = getattr(experiment, "LICENSE", None)
    if authors:
        if isinstance(authors, (list, tuple)):
            authors = ", ".join(str(a) for a in authors)
        else:
            authors = str(authors)

    if isinstance(start, datetime.datetime) and isinstance(end, datetime.datetime):
        date_range = f"{start.date()} — {end.date()}"
    else:
        date_range = "?"

    magnitudes = list(getattr(experiment, "magnitudes", []))
    region = getattr(experiment, "region", None)

    tw_raw: List[Any] = list(getattr(experiment, "time_windows", []))
    tw_all: List[str] = []
    for tw in tw_raw:
        tw_all.append(timewindow2str(tw).replace("_", " to "))

    models: List[Dict[str, Any]] = []
    model_objs = getattr(experiment, "models", [])
    model_names = [i.name for i in model_objs]
    for model in getattr(experiment, "models", []):
        model_registry = model.registry

        model_forecasts: Dict[str, str] = {}
        for tw_obj, tw_str in zip(tw_raw, tw_all):
            try:
                fc_path = model_registry.get_forecast_key(tw_obj)
            except Exception:
                continue

            rel_fc = _rel(fc_path, app_root)
            model_forecasts[tw_str] = rel_fc

        models.append(
            {
                "name": getattr(model, "name", None),
                "forecast_unit": getattr(model, "forecast_unit", None),
                "path": model_registry.rel(model_registry.path) or None,
                "giturl": getattr(model, "giturl", None),
                "git_hash": getattr(model, "repo_hash", None),
                "zenodo_id": getattr(model, "zenodo_id", None),
                "authors": getattr(model, "authors", None),
                "doi": getattr(model, "doi", None),
                "func": getattr(model, "func", None),
                "func_kwargs": getattr(model, "func_kwargs", None),
                "fmt": getattr(model, "fmt", None),
                "registry": model_registry,
                "forecasts": model_forecasts,
                "forecast_class": model.repository.__class__.__name__,
            }
        )

    tests: List[Dict] = []
    test_objs = getattr(experiment, "tests", [])
    test_names = [i.name for i in getattr(experiment, "tests", [])]
    for test, test_name in zip(test_objs, test_names):
        func_obj = getattr(test, "func", None)
        mod_name = getattr(func_obj, "__module__", None)
        func_name = getattr(func_obj, "__name__", None)

        if mod_name is not None and func_name is not None:
            func_str = f"{mod_name}.{func_name}"
        elif func_name is not None:
            func_str = func_name
        else:
            func_str = None

        tests.append(
            {
                "name": test_name,
                "func": func_str,
                "func_kwargs": getattr(test, "func_kwargs", None),
                "ref_model": getattr(test, "ref_model", None),
                "plot_func": getattr(test, "plot_func", None),
                "plot_args": getattr(test, "plot_args", None),
                "plot_kwargs": getattr(test, "plot_kwargs", None),
            }
        )

    catalog: Dict[str, str] = {}
    try:
        cat_map = reg.get_figure_key("main_catalog_map")
        cat_time = reg.get_figure_key("main_catalog_time")
        cat_path = _rel(reg.run_dir / cat_repo.cat_path, app_root)
        catalog["path"] = cat_path
        catalog["map"] = _rel(cat_map, app_root)
        catalog["time"] = _rel(cat_time, app_root)
    except Exception:
        pass

    results_main: Dict[Tuple[str, str], str] = {}
    results_model: Dict[Tuple[str, str, str], str] = {}

    for tw_obj, tw_str in zip(tw_raw, tw_all):
        for test_name in test_names:
            try:
                p = reg.get_figure_key(tw_obj, test_name)
                results_main[(tw_str, test_name)] = _rel(p, app_root)
            except Exception:
                pass
            for model_name in model_names:
                try:
                    p = reg.get_figure_key(tw_obj, f"{test_name}_{model_name}")
                    if reg.file_exists("figures", tw_obj, f"{test_name}_{model_name}"):
                        results_model[(tw_str, test_name, model_name)] = _rel(p, app_root)
                except Exception:
                    continue

    time_cfg: Dict[str, Any] = getattr(experiment, "time_config", {}) or {}
    region_cfg: Dict[str, Any] = getattr(experiment, "region_config", {}) or {}

    exp_class_code = time_cfg.get("exp_class", getattr(experiment, "exp_class", "ti"))
    exp_class = (
        "Time-Dependent" if exp_class_code in ("td", "time-dependent") else "Time-Independent"
    )

    n_intervals = time_cfg.get("intervals") or len(time_cfg.get("time_windows", [])) or 0
    horizon_str = _timedelta_to_str(time_cfg.get("horizon"))
    offset_str = _timedelta_to_str(time_cfg.get("offset"))
    growth = time_cfg.get("growth")

    mag_min = getattr(experiment, "mag_min", None)
    mag_max = getattr(experiment, "mag_max", None)
    mag_bin = getattr(experiment, "mag_bin", None)
    depth_min = getattr(experiment, "depth_min", None)
    depth_max = getattr(experiment, "depth_max", None)

    run_mode = getattr(experiment, "run_mode", None)
    run_dir = getattr(experiment, "run_dir", None)
    config_file = getattr(experiment, "config_file", None)
    model_config_path = getattr(experiment, "model_config", None)
    test_config_path = getattr(experiment, "test_config", None)
    return Manifest(
        name=name,
        start_date=start.date().isoformat(),
        end_date=end.date().isoformat(),
        authors=authors,
        journal=getattr(experiment, "journal", None),
        manuscript_doi=getattr(experiment, "manuscript_doi", None),
        floatcsep_version=getattr(experiment, "floatcsep_version", None),
        pycsep_version=getattr(experiment, "pycsep_version", None),
        last_run=getattr(experiment, "last_run", None),
        exp_time=getattr(experiment, "exp_time", None),
        doi=doi,
        catalog_doi=catalog_doi,
        license=license_,
        date_range=date_range,
        magnitudes=magnitudes,
        region=region,
        models=models,
        tests=tests,
        time_windows=tw_all,
        catalog=catalog,
        results_main=results_main,
        results_model=results_model,
        app_root=str(app_root),
        # new metadata fields
        exp_class=exp_class,
        n_intervals=n_intervals,
        horizon=horizon_str,
        offset=offset_str,
        growth=growth,
        mag_min=mag_min,
        mag_max=mag_max,
        mag_bin=mag_bin,
        depth_min=depth_min,
        depth_max=depth_max,
        run_mode=run_mode,
        run_dir=run_dir,
        config_file=config_file,
        model_config=model_config_path,
        test_config=test_config_path,
    )
