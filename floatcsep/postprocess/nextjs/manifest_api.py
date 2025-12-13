"""
Python subprocess handlers for complex data processing.
Called by Next.js API routes via subprocess.
"""
import sys
import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, List

from floatcsep.utils.file_io import GriddedForecastParsers, CatalogForecastParsers, CatalogParser


def load_catalog_data(catalog_path: str, app_root: str) -> Dict[str, Any]:
    """Load catalog and return event data as JSON."""
    path = Path(app_root) / catalog_path

    try:
        if path.suffix.lower() == ".json":
            try:
                catalog = CatalogParser.json(str(path))
            except json.JSONDecodeError:
                catalog = CatalogParser.ascii(str(path))
        else:
            catalog = CatalogParser.ascii(str(path))
    except Exception as e:
        return {"error": str(e)}

    if catalog is None or catalog.event_count == 0:
        return {"events": [], "count": 0, "bbox": None}

    lons = catalog.get_longitudes()
    lats = catalog.get_latitudes()
    mags = catalog.get_magnitudes()
    dts = catalog.get_datetimes()
    event_ids = catalog.get_event_ids()

    events = []
    for i in range(len(lons)):
        events.append({
            "lon": float(lons[i]),
            "lat": float(lats[i]),
            "magnitude": float(mags[i]),
            "time": dts[i].isoformat(),
            "event_id": str(event_ids[i]) if isinstance(event_ids[i], (bytes, bytearray)) else event_ids[i].decode('utf-8') if hasattr(event_ids[i], 'decode') else str(event_ids[i]),
        })

    try:
        bbox = list(catalog.get_bbox())
    except Exception:
        bbox = None

    return {
        "events": events,
        "count": catalog.event_count,
        "bbox": bbox,
    }


def load_forecast_data(
    forecast_path: str,
    app_root: str,
    region_data: Dict[str, Any],
    is_catalog_fc: bool = False,
) -> Dict[str, Any]:
    """Load forecast and return gridded data as JSON."""
    path = Path(app_root) / forecast_path

    if not path.exists():
        return {"error": f"Forecast file not found: {forecast_path}"}

    suffix = path.suffix.lower()

    try:
        if is_catalog_fc:
            # For catalog forecasts, we need the region
            from pycsep.core.regions import CartesianGrid2D

            # Reconstruct region from data
            if not region_data or not region_data.get('bbox'):
                return {"error": "Region data required for catalog forecasts"}

            bbox = region_data['bbox']
            dh = region_data.get('dh', 0.1)

            # Create region
            region = CartesianGrid2D.from_origins(
                origins=None,
                dh=dh,
                mask=None,
            )

            # Load catalog forecast
            cf = CatalogForecastParsers.csv(
                str(path),
                region=region,
                filter_spatial=True,
                apply_filters=True,
                store=False,
            )

            gf = cf.get_expected_rates(verbose=False)
            rates = np.asarray(gf.data, dtype='float32')
            region_out = getattr(gf, 'region', region)
            mags = np.asarray(getattr(gf, 'magnitudes', []))
        else:
            # Gridded forecast
            if suffix == ".dat":
                rates, region_out, mags = GriddedForecastParsers.dat(str(path))
            elif suffix in (".xml", ".gml"):
                rates, region_out, mags = GriddedForecastParsers.xml(str(path))
            elif suffix in (".csv", ".txt"):
                rates, region_out, mags = GriddedForecastParsers.csv(str(path))
            elif suffix in (".h5", ".hdf5"):
                rates, region_out, mags = GriddedForecastParsers.hdf5(str(path))
            else:
                return {"error": f"Unsupported forecast file extension: {suffix}"}

        # Sum across magnitude bins to get total rate per cell
        total_rates = rates.sum(axis=1).astype('float32')

        # Get cell coordinates
        origins = region_out.origins()
        dh = float(region_out.dh)

        lon_min = origins[:, 0]
        lat_min = origins[:, 1]
        lon_c = lon_min + 0.5 * dh
        lat_c = lat_min + 0.5 * dh

        # Build cell data
        cells = []
        for i in range(len(lon_c)):
            if total_rates[i] > 0:
                cells.append({
                    "lon": float(lon_c[i]),
                    "lat": float(lat_c[i]),
                    "rate": float(total_rates[i]),
                    "width": float(dh),
                    "height": float(dh),
                })

        # Calculate vmin/vmax in log10 space
        with np.errstate(divide='ignore', invalid='ignore'):
            log_rates = np.where(total_rates > 0, np.log10(total_rates), np.nan)

        finite = np.isfinite(log_rates)
        if np.any(finite):
            vmin = float(np.nanmin(log_rates[finite]))
            vmax = float(np.nanmax(log_rates[finite]))
        else:
            vmin = 0.0
            vmax = 1.0

        return {
            "cells": cells,
            "vmin": vmin,
            "vmax": vmax,
        }

    except Exception as e:
        return {"error": f"Failed to load forecast: {str(e)}"}


if __name__ == "__main__":
    # Command-line interface for subprocess calls
    if len(sys.argv) < 2:
        print(json.dumps({"error": "No command specified"}))
        sys.exit(1)

    command = sys.argv[1]

    if command == "load_catalog":
        if len(sys.argv) < 4:
            print(json.dumps({"error": "Missing arguments for load_catalog"}))
            sys.exit(1)
        catalog_path = sys.argv[2]
        app_root = sys.argv[3]
        result = load_catalog_data(catalog_path, app_root)
        print(json.dumps(result))

    elif command == "load_forecast":
        if len(sys.argv) < 6:
            print(json.dumps({"error": "Missing arguments for load_forecast"}))
            sys.exit(1)
        forecast_path = sys.argv[2]
        app_root = sys.argv[3]
        region_data = json.loads(sys.argv[4])
        is_catalog_fc = sys.argv[5].lower() == "true"
        result = load_forecast_data(forecast_path, app_root, region_data, is_catalog_fc)
        print(json.dumps(result))

    else:
        print(json.dumps({"error": f"Unknown command: {command}"}))
        sys.exit(1)
