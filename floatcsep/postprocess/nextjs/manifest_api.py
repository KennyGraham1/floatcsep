"""
Data loaders for the floatCSEP Next.js dashboard.

The dashboard API routes (``lib/server/python.ts``) run this module as a subprocess
with the same Python interpreter that launched ``floatcsep view``. Each command parses
a catalog or forecast with floatCSEP's own parsers and writes a compact, columnar JSON
document to ``--out``. A one-line JSON status is printed to stdout. Caching is done by
the caller, keyed on the source file's path, size and modification time.

Usage::

    python manifest_api.py catalog --path <catalog file> --out <json>
    python manifest_api.py forecast --manifest <manifest.json> --model <i> --window <j> \
        --out <json>
    python manifest_api.py rates --manifest <manifest.json> --model <i> --out <f32>

Forecasts evaluated outside floatCSEP (``external`` models, see
``schemas.external_models``) can cover millions of cells: their forecast document
describes the grid, and ``rates`` writes the rate of every cell, per forecast unit,
as little-endian float32 values, which the dashboard scales to each time window.
"""

import argparse
import calendar
import datetime
import hashlib
import json
import math
import os
import sys
import traceback
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Bump when the JSON layout changes, so cached documents are regenerated.
FORMAT_VERSION = 5


def _write_json(payload: Dict[str, Any], out_path: str) -> None:
    """Write JSON atomically, so a concurrent reader never sees a partial file."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(f".{out.name}.{os.getpid()}.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, separators=(",", ":"), allow_nan=False)
    os.replace(tmp, out)


def _decode(value: Any) -> str:
    if isinstance(value, (bytes, bytearray, np.bytes_)):
        return bytes(value).decode("utf-8", errors="replace")
    return str(value)


def _rounded(values: np.ndarray, decimals: int) -> List[Optional[float]]:
    """Round an array and map non-finite values to None (JSON has no NaN)."""
    values = np.asarray(values, dtype=float)
    out = np.round(values, decimals).tolist()
    if np.isfinite(values).all():
        return out
    return [v if math.isfinite(v) else None for v in out]


def _significant(values: np.ndarray, digits: int = 6) -> List[float]:
    return [float(f"{v:.{digits}g}") for v in np.asarray(values, dtype=float)]


def load_catalog(path: str) -> Dict[str, Any]:
    """Parse an observed catalog into columnar arrays (times in epoch milliseconds)."""
    from floatcsep.utils.file_io import CatalogParser

    catalog_path = Path(path)
    if not catalog_path.is_file():
        raise FileNotFoundError(f"Catalog file not found: {catalog_path}")

    if catalog_path.suffix.lower() == ".json":
        try:
            catalog = CatalogParser.json(str(catalog_path))
        except (json.JSONDecodeError, UnicodeDecodeError):
            catalog = CatalogParser.ascii(str(catalog_path))
    else:
        catalog = CatalogParser.ascii(str(catalog_path))

    count = 0 if catalog is None else int(catalog.event_count)
    if count == 0:
        return {
            "version": FORMAT_VERSION,
            "count": 0,
            "lon": [],
            "lat": [],
            "mag": [],
            "depth": [],
            "time": [],
            "id": [],
        }

    return {
        "version": FORMAT_VERSION,
        "count": count,
        "lon": _rounded(catalog.get_longitudes(), 5),
        "lat": _rounded(catalog.get_latitudes(), 5),
        "mag": _rounded(catalog.get_magnitudes(), 3),
        "depth": _rounded(catalog.get_depths(), 3),
        "time": [int(t) for t in catalog.get_epoch_times()],
        "id": [_decode(i) for i in catalog.get_event_ids()],
    }


def _experiment_region(manifest: Dict[str, Any]):
    """Rebuild the experiment's space-magnitude region from the manifest."""
    from csep.core.regions import CartesianGrid2D

    region = manifest.get("region") or {}
    origins = region.get("origins")
    dh = region.get("dh")
    magnitudes = manifest.get("magnitudes") or []
    if not origins or not dh:
        raise ValueError("The manifest has no region grid, required for catalog forecasts.")
    if len(magnitudes) == 0:
        raise ValueError("The manifest has no magnitude bins, required for catalog forecasts.")
    return CartesianGrid2D.from_origins(
        np.asarray(origins, dtype=float),
        dh=float(dh),
        magnitudes=np.asarray(magnitudes, dtype=float),
        name=region.get("name"),
    )


def _load_gridded(path: Path, fmt: Optional[str]):
    from floatcsep.utils.file_io import GriddedForecastParsers

    suffix = path.suffix.lower().lstrip(".") or (fmt or "").lower().lstrip(".")
    parsers = {
        "dat": GriddedForecastParsers.dat,
        "xml": GriddedForecastParsers.xml,
        "gml": GriddedForecastParsers.xml,
        "csv": GriddedForecastParsers.csv,
        "txt": GriddedForecastParsers.csv,
        "h5": GriddedForecastParsers.hdf5,
        "hdf5": GriddedForecastParsers.hdf5,
    }
    if suffix not in parsers:
        raise ValueError(f"Unsupported gridded forecast format: '.{suffix}'")
    rates, region, magnitudes = parsers[suffix](str(path))
    return np.asarray(rates, dtype=float), region, np.asarray(magnitudes, dtype=float)


def _decimal_year(moment: datetime.datetime) -> float:
    """
    pyCSEP's csep.utils.time_utils.decimal_year, term by term, so that the scale is
    identical, without importing pyCSEP, which takes seconds for every forecast shown.
    """
    days_in_year = 366.0 if calendar.isleap(moment.year) else 365.0
    days_before = sum(calendar.monthrange(moment.year, m)[1] for m in range(1, moment.month))
    return (
        moment.year
        + (
            days_before
            + (moment.day - 1)
            + moment.hour / 24.0
            + moment.minute / 1440.0
            + (moment.second + moment.microsecond * 1e-6) / 86400.0
        )
        / days_in_year
    )


def _forecast_unit(model: Dict[str, Any]) -> Any:
    """
    The forecast unit floatCSEP applies to a model's gridded forecasts: the configured
    one for time-independent models, while time-dependent models are always loaded with
    a unit of 1 year (TimeDependentModel.get_forecast passes none).
    """
    return None if model.get("time_dependent") else model.get("forecast_unit")


def _window_scale(window: str, forecast_unit: Any) -> float:
    """
    Scale floatCSEP applies to gridded forecasts: window length in decimal years
    over the model's forecast unit (1 year unless configured, see
    GriddedForecastRepository._load_single_forecast). The window is parsed as
    floatcsep.utils.helpers.str2timewindow does.
    """
    start, end = (
        datetime.datetime.fromisoformat(part) for part in window.replace(" to ", "_").split("_")
    )
    unit = float(forecast_unit) if forecast_unit else 1.0
    return (_decimal_year(end) - _decimal_year(start)) / unit


def _forecast_source(manifest_path: str, model_index: int, window_index: int):
    """The manifest entry of a model, the time window and the forecast file."""
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    models = manifest.get("models") or []
    windows = manifest.get("time_windows") or []
    if not 0 <= model_index < len(models):
        raise IndexError(f"Model index {model_index} is out of range")
    if not 0 <= window_index < len(windows):
        raise IndexError(f"Time window index {window_index} is out of range")

    model = models[model_index]
    window = windows[window_index]
    rel_path = (model.get("forecasts") or {}).get(window)
    if not rel_path:
        raise LookupError(f"Model '{model.get('name')}' has no forecast for {window}")

    app_root = Path(manifest.get("app_root") or Path(manifest_path).parent)
    path = (app_root / rel_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Forecast file not found: {rel_path}")
    return manifest, model, window, rel_path, path


def _external_array(model: Dict[str, Any], path: Path) -> np.ndarray:
    """
    An external forecast, memory-mapped, after checking it against its declaration:
    one row per cell of the grid and, if magnitudes are declared, one column per bin.
    """
    grid = model["external"]["grid"]
    data = np.load(path, mmap_mode="r")
    cells = int(grid["nx"]) * int(grid["ny"])
    bins = len(model["external"].get("magnitudes") or [])
    if data.ndim != 2 or data.shape[0] != cells or (bins and data.shape[1] != bins):
        expected = f"({cells}, {bins})" if bins else f"({cells}, bins)"
        raise ValueError(
            f"{path.name} has shape {data.shape}, but its grid and magnitudes in "
            f"external_forecasts.json give {expected}"
        )
    return data


def _sum_external(data: np.ndarray):
    """The rates of every cell (summed over magnitude bins) and of every bin."""
    return (
        np.asarray(data.sum(axis=1), dtype=float),
        np.asarray(data.sum(axis=0), dtype=float),
    )


def _external_sums(data: np.ndarray, path: Path, cache_dir: Optional[Path]):
    """
    An external forecast summed over the magnitude bins (per cell) and over the cells (per
    bin), per forecast unit. Reading the whole array takes seconds, and the sums do not
    depend on the time window, so they are kept in the dashboard's cache.
    """
    saved = None
    if cache_dir is not None:
        stat = path.stat()
        identity = f"{path.resolve()}:{stat.st_mtime_ns}:{stat.st_size}"
        saved = Path(cache_dir) / f"sums-{hashlib.sha1(identity.encode()).hexdigest()}.npz"
        try:
            with np.load(saved) as sums:
                return sums["cells"], sums["magnitudes"]
        except FileNotFoundError:
            pass  # not saved yet
        except Exception:  # unreadable (e.g. truncated): drop it and compute again
            try:
                saved.unlink()
            except OSError:
                pass
    cells, magnitudes = _sum_external(data)
    if saved is not None:
        saved.parent.mkdir(parents=True, exist_ok=True)
        tmp = saved.with_name(f"{saved.stem}.{os.getpid()}.tmp.npz")
        np.savez(tmp, cells=cells, magnitudes=magnitudes)
        os.replace(tmp, saved)
    return cells, magnitudes


def _load_external(
    model: Dict[str, Any],
    window: str,
    rel_path: str,
    path: Path,
    cache_dir: Optional[Path] = None,
):
    """A forecast array on a regular grid of every cell (see schemas.external_models)."""
    grid = model["external"]["grid"]
    cells, magnitudes = _external_sums(_external_array(model, path), path, cache_dir)
    scale = _window_scale(window, _forecast_unit(model))
    cell_rates = cells * scale
    magnitude_rates = magnitudes * scale
    positive = cell_rates[np.isfinite(cell_rates) & (cell_rates > 0)]
    log_rates = np.log10(positive) if positive.size else np.array([0.0, 1.0])
    return {
        "version": FORMAT_VERSION,
        "kind": "gridded",
        "grid": "dense",
        "lon0": float(grid["lon0"]),
        "lat0": float(grid["lat0"]),
        "dh": float(grid["dh"]),
        "nx": int(grid["nx"]),
        "ny": int(grid["ny"]),
        "order": grid.get("order", "lon-major"),
        # The cell rates come from the `rates` command, per forecast unit
        "rate_scale": scale,
        "model": model.get("name"),
        "time_window": window,
        "path": rel_path,
        "n_cells": int(cell_rates.size),
        "n_active": int(positive.size),
        "rate": [],
        "total": float(np.nansum(cell_rates)),
        "vmin": float(log_rates.min()),
        "vmax": float(log_rates.max()),
        "magnitudes": _rounded(np.asarray(model["external"].get("magnitudes") or [], float), 4),
        "magnitude_rates": _significant(magnitude_rates),
        "n_catalogs": None,
    }


def write_rates(
    manifest_path: str, model_index: int, out_path: str, window_index: int = 0
) -> None:
    """The rate of every cell of an external forecast, per forecast unit, as float32."""
    _, model, _, _, path = _forecast_source(manifest_path, model_index, window_index)
    if not model.get("external"):
        raise ValueError(f"Model '{model.get('name')}' is not an external forecast")
    cells, _ = _external_sums(_external_array(model, path), path, Path(out_path).parent)
    rates = cells.astype("<f4")
    tmp = f"{out_path}.{os.getpid()}.tmp"
    rates.tofile(tmp)
    os.replace(tmp, out_path)


def load_forecast(
    manifest_path: str,
    model_index: int,
    window_index: int,
    cache_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """Expected rates of one model and time window, as a sparse grid of cell rates."""
    manifest, model, window, rel_path, path = _forecast_source(
        manifest_path, model_index, window_index
    )
    if model.get("external"):
        return _load_external(model, window, rel_path, path, cache_dir)

    is_catalog = model.get("forecast_class") == "CatalogForecastRepository"
    n_catalogs = None
    if is_catalog:
        from floatcsep.utils.file_io import CatalogForecastParsers

        region = _experiment_region(manifest)
        n_sims = (model.get("func_kwargs") or {}).get("n_sims")
        forecast = CatalogForecastParsers.csv(
            str(path),
            region=region,
            n_cat=int(n_sims) if n_sims else None,
            filter_spatial=True,
            apply_filters=True,
            store=False,
        )
        expected = forecast.get_expected_rates(verbose=False)
        rates = np.asarray(expected.data, dtype=float)
        magnitudes = np.asarray(region.magnitudes, dtype=float)
        n_catalogs = int(forecast.n_cat) if forecast.n_cat is not None else None
    else:
        rates, region, magnitudes = _load_gridded(path, model.get("fmt"))
        # Match what the experiment evaluates: rates for this window's length.
        rates = rates * _window_scale(window, _forecast_unit(model))

    if rates.ndim == 1:
        rates = rates[:, None]
    cell_rates = rates.sum(axis=1)
    magnitude_rates = rates.sum(axis=0)
    active = np.isfinite(cell_rates) & (cell_rates > 0)
    log_rates = np.log10(cell_rates[active]) if active.any() else np.array([0.0, 1.0])

    if hasattr(region, "quadkeys"):
        # Multi-resolution quadtree: cells are Web Mercator tiles.
        quadkeys = np.asarray(region.quadkeys).astype(str)
        grid = {"grid": "quadtree", "quadkeys": quadkeys[active].tolist()}
    else:
        grid = _regular_grid(region, active)

    return {
        "version": FORMAT_VERSION,
        "kind": "catalog" if is_catalog else "gridded",
        **grid,
        "model": model.get("name"),
        "time_window": window,
        "path": rel_path,
        "n_cells": int(len(cell_rates)),
        "n_active": int(active.sum()),
        "rate": _significant(cell_rates[active]),
        "total": float(np.nansum(cell_rates)),
        "vmin": float(log_rates.min()),
        "vmax": float(log_rates.max()),
        "magnitudes": _rounded(magnitudes, 4),
        "magnitude_rates": _significant(magnitude_rates),
        "n_catalogs": n_catalogs,
    }


def _regular_grid(region, active: np.ndarray) -> Dict[str, Any]:
    """Integer cell positions of a CartesianGrid2D, from its lower-left corner."""
    origins = np.asarray(region.origins(), dtype=float)
    dh = float(region.dh)
    lon = origins[:, 0]
    lat = origins[:, 1]
    # Keep regions that straddle the antimeridian contiguous (e.g. 179°E -> 181°E).
    if lon.max() - lon.min() > 180:
        shifted = np.where(lon < 0, lon + 360.0, lon)
        if shifted.max() - shifted.min() < lon.max() - lon.min():
            lon = shifted
    lon0 = float(lon.min())
    lat0 = float(lat.min())
    ix = np.rint((lon - lon0) / dh).astype(np.int64)
    iy = np.rint((lat - lat0) / dh).astype(np.int64)
    return {
        "grid": "regular",
        "dh": dh,
        "lon0": lon0,
        "lat0": lat0,
        "nx": int(ix.max()) + 1,
        "ny": int(iy.max()) + 1,
        "ix": ix[active].tolist(),
        "iy": iy[active].tolist(),
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    catalog = sub.add_parser("catalog", help="Parse an observed catalog")
    catalog.add_argument("--path", required=True)
    catalog.add_argument("--out", required=True)

    forecast = sub.add_parser("forecast", help="Compute cell rates of a forecast")
    forecast.add_argument("--manifest", required=True)
    forecast.add_argument("--model", type=int, required=True)
    forecast.add_argument("--window", type=int, required=True)
    forecast.add_argument("--out", required=True)

    rates = sub.add_parser("rates", help="Write the cell rates of an external forecast")
    rates.add_argument("--manifest", required=True)
    rates.add_argument("--model", type=int, required=True)
    rates.add_argument("--window", type=int, default=0)
    rates.add_argument("--out", required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            _write_json(load_catalog(args.path), args.out)
        elif args.command == "rates":
            write_rates(args.manifest, args.model, args.out, args.window)
        else:
            document = load_forecast(
                args.manifest, args.model, args.window, Path(args.out).parent
            )
            _write_json(document, args.out)
    except Exception as exc:  # reported to the dashboard as a JSON error
        traceback.print_exc(file=sys.stderr)
        print(json.dumps({"ok": False, "error": str(exc) or exc.__class__.__name__}))
        return 1

    print(json.dumps({"ok": True, "out": args.out}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
