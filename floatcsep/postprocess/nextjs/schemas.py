"""Pydantic schemas for floatCSEP Next.js dashboard."""

import datetime
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from pydantic import BaseModel, ConfigDict, Field, field_validator

logger = logging.getLogger(__name__)

# Model entries carry floatCSEP internals (e.g. the file registry) that are not
# experiment metadata and must not be dumped into the manifest.
EXCLUDED_MODEL_KEYS = ("registry",)

# The browser indexes the columns and rows of an external grid with 16-bit integers and
# needs about 40 bytes per cell (the global 0.1-degree grid, 6.48 million cells, 270 MB).
MAX_GRID_SIDE = 65535
MAX_GRID_CELLS = 2**24


def _number(value: Any) -> bool:
    """A finite JSON number (booleans and strings are not)."""
    return (
        isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    )


def _checked_grid(spec: Any) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """
    The grid of an external_forecasts.json, normalised as the dashboard reads it (numbers,
    and whole numbers of columns and rows), or why it cannot be mapped.
    """
    grid = spec.get("grid") if isinstance(spec, dict) else None
    if not isinstance(grid, dict):
        return None, "no grid"
    values = [grid.get(key) for key in ("lon0", "lat0", "dh", "nx", "ny")]
    if not all(_number(v) for v in values):
        return None, "lon0, lat0, dh, nx and ny must be finite numbers"
    lon0, lat0, dh, nx, ny = values
    if dh <= 0:
        return None, "dh must be positive"
    if not all(float(v).is_integer() and 0 < v <= MAX_GRID_SIDE for v in (nx, ny)):
        return None, f"nx and ny must be whole numbers from 1 to {MAX_GRID_SIDE}"
    nx, ny = int(nx), int(ny)
    if nx * ny > MAX_GRID_CELLS:
        return None, f"{nx * ny:,} cells, more than the {MAX_GRID_CELLS:,} a browser can map"
    order = grid.get("order", "lon-major")
    if order != "lon-major":
        return None, 'order must be "lon-major"'
    magnitudes = spec.get("magnitudes")
    if magnitudes is not None and not (
        isinstance(magnitudes, list) and all(_number(m) for m in magnitudes)
    ):
        return None, "magnitudes must be a list of numbers"
    name = str(grid.get("name", "external"))
    return {
        "name": name,
        "lon0": float(lon0),
        "lat0": float(lat0),
        "dh": float(dh),
        "nx": nx,
        "ny": ny,
        "order": order,
    }, None


def external_models(declaration: Path, time_windows: List[str]) -> List[Dict[str, Any]]:
    """
    Forecasts evaluated outside floatCSEP that the dashboard maps too, declared in an
    external_forecasts.json next to the configuration (e.g. written by Tutorial K's
    native_grid.py)::

        {"grid": {"name": "FULL01", "lon0": -180, "lat0": -90, "dh": 0.1,
                  "nx": 3600, "ny": 1800, "order": "lon-major"},
         "magnitudes": [...], "forecast_unit": 1,
         "forecasts": {"GEAR1": "/path/GEAR1_01deg_rates.npy",
                       "PPE": {"2014-01-01_2015-01-01": "/path/PPE_2014.npy", ...}, ...}}

    Each .npy array holds the expected events per forecast_unit years of every cell
    of the grid (in `order`) and magnitude bin: one for every time window, or one per
    window (named as floatCSEP names them) for a model whose forecast varies in time.
    The models are named <MODEL>=<grid>.
    """
    declaration = Path(declaration)
    if not declaration.is_file():
        return []
    spec = json.loads(declaration.read_text())
    grid, problem = _checked_grid(spec)
    if problem:
        logger.warning(f"Ignoring {declaration}: {problem}")
        return []
    models = []

    def resolve(file: str) -> str:
        return str((declaration.parent / file).resolve())

    for name, file in spec.get("forecasts", {}).items():
        if isinstance(file, dict):  # a forecast per time window: "<start>_<end>" keys
            by_window = {str(w).replace("_", " to "): resolve(f) for w, f in file.items()}
            forecasts = {w: by_window[w] for w in time_windows if w in by_window}
        else:
            forecasts = {w: resolve(file) for w in time_windows}
        if not forecasts:
            continue
        path = next(iter(forecasts.values()))
        models.append(
            {
                "name": f"{name}={grid['name']}",
                "forecast_unit": spec.get("forecast_unit", 1),
                "path": path,
                "fmt": "npy",
                "forecast_class": "ExternalGridForecast",
                "forecasts": forecasts,
                "external": {"grid": grid, "magnitudes": spec.get("magnitudes")},
            }
        )
    return models


def _callable_name(value: Any) -> str:
    """Return the dotted import name of a function or class."""
    module = getattr(value, "__module__", None)
    name = getattr(value, "__qualname__", None) or getattr(value, "__name__", None)
    if not name:
        return repr(value)
    return f"{module}.{name}" if module else name


def serialize_value_recursive(value: Any) -> Any:
    """Recursively convert values to JSON-serializable types."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return serialize_value_recursive(value.tolist())
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    if isinstance(value, datetime.timedelta):
        return str(value)
    if isinstance(value, dict):
        return {str(k): serialize_value_recursive(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [serialize_value_recursive(v) for v in value]
    if callable(value):
        # Functions (e.g. a test's plot functions) are identified by name.
        return _callable_name(value)
    if hasattr(value, "__dict__"):
        return serialize_value_recursive(vars(value))
    return str(value)


def finite_json(value: Any) -> Any:
    """Replace NaN/Infinity (invalid in JSON) with None, recursively."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: finite_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [finite_json(v) for v in value]
    return value


class ManifestModel(BaseModel):
    """
    Pydantic model for the Experiment Manifest.
    Validates and serializes the Manifest dataclass from floatcsep.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    # --- Existing fields ---
    name: str
    start_date: str
    end_date: str
    authors: Optional[str] = None
    doi: Optional[str] = None
    journal: Optional[str] = None
    manuscript_doi: Optional[str] = None
    exp_time: Optional[str] = None
    floatcsep_version: Optional[str] = None
    pycsep_version: Optional[str] = None
    last_run: Optional[str] = None
    catalog_doi: Optional[str] = None
    license: Optional[str] = None
    date_range: str
    magnitudes: List[float]

    # Region is typically an object in the dataclass
    region: Optional[Dict[str, Any]] = None

    models: List[Dict[str, Any]]
    tests: List[Dict[str, Any]]
    time_windows: List[str]

    catalog: Dict[str, Any]
    results_main: Dict[str, str]  # Key will be converted to string pipe-delimited
    results_model: Dict[str, str]

    app_root: Optional[str] = None

    # --- Metadata fields ---
    exp_class: str
    n_intervals: int
    horizon: Optional[str] = None
    offset: Optional[str] = None
    growth: Optional[str] = None

    mag_min: Optional[float] = None
    mag_max: Optional[float] = None
    mag_bin: Optional[float] = None
    depth_min: Optional[float] = None
    depth_max: Optional[float] = None

    run_mode: Optional[str] = None
    run_dir: Optional[str] = None
    config_file: Optional[str] = None
    # Rename to avoid conflict with Pydantic's model_config
    model_config_path: Optional[str] = Field(
        None, validation_alias="model_config", serialization_alias="model_config"
    )
    test_config: Optional[str] = None
    # Markdown describing the experiment (about.md next to the configuration)
    about: Optional[str] = None

    @field_validator("region", mode="before")
    def serialize_region(cls, v: Any) -> Optional[Dict[str, Any]]:
        if v is None:
            return None
        if isinstance(v, dict):
            return serialize_value_recursive(v)
        # Attempt to extract attributes from Region object
        return {
            "name": getattr(v, "name", None),
            "bbox": [float(x) for x in v.get_bbox()] if hasattr(v, "get_bbox") else None,
            "dh": float(v.dh) if hasattr(v, "dh") else None,
            "origins": v.origins().tolist() if hasattr(v, "origins") else None,
        }

    @field_validator("models", mode="before")
    def serialize_models(cls, v: Any) -> Any:
        if isinstance(v, (list, tuple)):
            v = [
                (
                    {k: val for k, val in m.items() if k not in EXCLUDED_MODEL_KEYS}
                    if isinstance(m, dict)
                    else m
                )
                for m in v
            ]
        return serialize_value_recursive(v)

    @field_validator("tests", "catalog", mode="before")
    def serialize_generic_structures(cls, v: Any) -> Any:
        return serialize_value_recursive(v)

    @field_validator("magnitudes", mode="before")
    def serialize_magnitudes(cls, v: Any) -> Any:
        return [float(m) for m in v] if v is not None else []

    @field_validator("results_main", mode="before")
    def serialize_results_main(cls, v: Any) -> Dict[str, str]:
        # transform Dict[Tuple[str, str], str] -> Dict[str, str]
        if isinstance(v, dict):
            new_dict = {}
            for key, val in v.items():
                if isinstance(key, tuple):
                    new_key = f"{key[0]}|{key[1]}"
                else:
                    new_key = str(key)
                new_dict[new_key] = serialize_value_recursive(val)
            return new_dict
        return v

    @field_validator("results_model", mode="before")
    def serialize_results_model(cls, v: Any) -> Dict[str, str]:
        # transform Dict[Tuple[str, str, str], str] -> Dict[str, str]
        if isinstance(v, dict):
            new_dict = {}
            for key, val in v.items():
                if isinstance(key, tuple):
                    new_key = f"{key[0]}|{key[1]}|{key[2]}"
                else:
                    new_key = str(key)
                new_dict[new_key] = serialize_value_recursive(val)
            return new_dict
        return v

    @field_validator(
        "app_root", "run_dir", "config_file", "model_config_path", "test_config", mode="before"
    )
    def serialize_paths(cls, v: Any) -> Optional[str]:
        if isinstance(v, Path):
            return str(v)
        return v

    @field_validator(
        "authors",
        "doi",
        "journal",
        "manuscript_doi",
        "exp_time",
        "floatcsep_version",
        "pycsep_version",
        "last_run",
        "catalog_doi",
        "license",
        "horizon",
        "offset",
        "growth",
        "run_mode",
        mode="before",
    )
    def serialize_optional_strings(cls, v: Any) -> Optional[str]:
        if v is None or isinstance(v, str):
            return v
        return str(serialize_value_recursive(v))

    @field_validator("mag_min", "mag_max", "mag_bin", "depth_min", "depth_max", mode="before")
    def serialize_optional_floats(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        v = float(v)
        return v if math.isfinite(v) else None
