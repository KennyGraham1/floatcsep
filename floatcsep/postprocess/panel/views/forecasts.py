from typing import Dict, Any, Optional, List

from pathlib import Path

import numpy as np
import panel as pn
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    LinearColorMapper,
    ColorBar,
)
from bokeh.palettes import Magma256

from ..manifest import Manifest
from .utils import build_region_basemap, lonlat_to_mercator, make_doi_badge
from floatcsep.utils.file_io import GriddedForecastParsers, CatalogForecastParsers
import logging

logger = logging.getLogger(__name__)

pn.extension()

_FORECAST_CACHE: Dict[Any, Any] = {}
_GLOBAL_FC_RANGE: Dict[str, Optional[float]] = {
    "low": None,
    "high": None,
    "initialized": None,
}


def make_magma_alpha_palette(
    alpha_exp: float = 0.0,
    alpha_0: Optional[float] = None,
) -> List[str]:
    base = list(Magma256)
    n = len(base)

    if alpha_0 is not None:
        a_arr = np.full(n, int(np.clip(alpha_0, 0.0, 1.0) * 255), dtype=int)
    elif alpha_exp != 0.0:
        a_arr = (np.linspace(0.05, 1.0, n) ** alpha_exp * 255).astype(int)
    else:
        a_arr = np.full(n, 255, dtype=int)

    palette: List[str] = []
    for color, a in zip(base, a_arr):
        r = color[1:3]
        g = color[3:5]
        b = color[5:7]
        aa = f"{a:02x}"
        palette.append(f"#{r}{g}{b}{aa}")
    return palette


def load_catalog_forecast_as_grid(
    path: Path,
    region: Any,
    nsims: Optional[int] = None,
) -> tuple[np.ndarray, Any, np.ndarray]:
    """
    Load a catalog-based forecast file and return a gridded representation:

        rates  : (n_cells, n_mags) float32 array of expected rates
        region : the region associated with the forecast (CartesianGrid2D)
        mags   : 1D array of magnitude bin edges

    This uses pyCSEP's CatalogForecast + get_expected_rates under the hood,
    but exposes only raw arrays to the dashboard.
    """
    if region is None:
        raise ValueError("Region is required to load a catalog-based forecast.")

    cf = CatalogForecastParsers.csv(
        path.as_posix(),
        region=region,
        filter_spatial=True,
        apply_filters=True,
        store=False,
    )

    if nsims is not None:
        cf.n_cat = nsims

    gf = cf.get_expected_rates(verbose=False)

    rates = np.asarray(gf.data, dtype="float32")
    region_out = getattr(gf, "region", region)
    mags = np.asarray(getattr(gf, "magnitudes", []))

    return rates, region_out, mags


def load_gridded_forecast(
    manifest: Manifest,
    model_index: int,
    timewindow_str: str,
) -> Dict[str, Any]:
    """
    Load and preprocess a gridded *or catalog-based* forecast for the dashboard.

    Returns a dict with:
        x, y:         cell centers (Web Mercator)
        width, height: cell sizes (Web Mercator)
        log10_rate:   log10(total rate) per cell (NaN where rate <= 0)
        mapper_meta:  dict with vmin, vmax in log10 space, or None
    """
    cache_key = (model_index, timewindow_str, "total")
    if cache_key in _FORECAST_CACHE:
        return _FORECAST_CACHE[cache_key]

    models: List[Dict[str, Any]] = getattr(manifest, "models", []) or []
    if model_index < 0 or model_index >= len(models):
        data = dict(x=[], y=[], width=[], height=[], log10_rate=[], mapper_meta=None)
        _FORECAST_CACHE[cache_key] = data
        return data

    model_cfg = models[model_index]
    fc_map = model_cfg.get("forecasts") or {}
    fc_rel = fc_map.get(timewindow_str)

    if not fc_rel:
        logger.warning(
            "No forecast file found for model '%s' (index %d), time window '%s'.",
            model_cfg.get("name", f"model_{model_index}"),
            model_index,
            timewindow_str,
        )
        data = dict(x=[], y=[], width=[], height=[], log10_rate=[], mapper_meta=None)
        _FORECAST_CACHE[cache_key] = data
        return data

    app_root = Path(getattr(manifest, "app_root", "."))
    fc_path = (app_root / fc_rel).resolve()
    suffix = fc_path.suffix.lower()

    func_kwargs = model_cfg.get("func_kwargs") or {}
    # Heuristic / convention: catalog-based forecasts
    is_catalog_fc = (
        model_cfg.get("forecast_class", "GriddedForecastRepository")
        == "CatalogForecastRepository"
    )
    try:
        if is_catalog_fc:
            # --- Catalog forecast path: use CatalogForecast + expected rates ---
            region = getattr(manifest, "region", None)
            if region is None:
                raise ValueError(
                    f"Cannot load catalog forecast '{fc_path}': manifest.region is None."
                )

            nsims = func_kwargs.get("n_sims")
            rates, region, mags = load_catalog_forecast_as_grid(
                fc_path,
                region=region,
                nsims=nsims,
            )

        else:
            # --- Classic gridded forecast path ---
            if suffix == ".dat":
                rates, region, mags = GriddedForecastParsers.dat(fc_path.as_posix())
            elif suffix in (".xml", ".gml"):
                rates, region, mags = GriddedForecastParsers.xml(fc_path.as_posix())
            elif suffix in (".csv", ".txt"):
                rates, region, mags = GriddedForecastParsers.csv(fc_path.as_posix())
            elif suffix in (".h5", ".hdf5"):
                rates, region, mags = GriddedForecastParsers.hdf5(fc_path.as_posix())
            else:
                logger.warning(
                    "Unsupported forecast file extension '%s' for '%s'. Skipping this forecast.",
                    suffix,
                    fc_path,
                )
                data = dict(x=[], y=[], width=[], height=[], log10_rate=[], mapper_meta=None)
                _FORECAST_CACHE[cache_key] = data
                return data

    except Exception as exc:
        logger.warning(
            "Failed to load forecast from '%s' (model '%s', window '%s'): %s",
            fc_path,
            model_cfg.get("name", f"model_{model_index}"),
            timewindow_str,
            exc,
        )
        data = dict(x=[], y=[], width=[], height=[], log10_rate=[], mapper_meta=None)
        _FORECAST_CACHE[cache_key] = data
        return data

    # From here on, treat both catalog-based and classic gridded forecasts identically
    total_rates = rates.sum(axis=1).astype("float32")

    origins = region.origins()
    dh = float(region.dh)

    lon_min = origins[:, 0]
    lat_min = origins[:, 1]
    lon_max = lon_min + dh
    lat_max = lat_min + dh

    lon_c = lon_min + 0.5 * dh
    lat_c = lat_min + 0.5 * dh

    x_c, y_c = lonlat_to_mercator(lon_c, lat_c)

    x_left, _ = lonlat_to_mercator(lon_min, lat_c)
    x_right, _ = lonlat_to_mercator(lon_max, lat_c)
    width = x_right - x_left

    _, y_bottom = lonlat_to_mercator(lon_c, lat_min)
    _, y_top = lonlat_to_mercator(lon_c, lat_max)
    height = y_top - y_bottom

    with np.errstate(divide="ignore", invalid="ignore"):
        log10_rate = np.where(total_rates > 0.0, np.log10(total_rates), np.nan).astype(
            "float32"
        )

    finite = np.isfinite(log10_rate)
    if np.any(finite):
        vmin = float(np.nanmin(log10_rate[finite]))
        vmax = float(np.nanmax(log10_rate[finite]))
        if vmax <= vmin:
            vmax = vmin + 1.0
        mapper_meta = {"vmin": vmin, "vmax": vmax}
    else:
        mapper_meta = None

    data = dict(
        x=x_c,
        y=y_c,
        width=width,
        height=height,
        log10_rate=log10_rate,
        mapper_meta=mapper_meta,
    )

    _FORECAST_CACHE[cache_key] = data
    return data


def build_model_options(manifest: Manifest) -> Dict[str, int]:
    """Build a label -> model_index mapping for the model select widget."""
    options: Dict[str, int] = {}
    models = getattr(manifest, "models", []) or []
    for i, model in enumerate(models):
        name = model.get("name") or f"Model {i+1}"
        options[name] = i
    return options


def build_timewindow_options(manifest: Manifest) -> Dict[str, str]:
    """Build a label -> timewindow_str mapping for the time-window select widget."""
    tw_strings = getattr(manifest, "time_windows", []) or []
    options: Dict[str, str] = {}
    for tw in tw_strings:
        label = tw
        options[label] = tw
    return options


def load_forecast_for_selection(
    manifest: Manifest,
    model_index: Optional[int],
    timewindow_str: Optional[str],
) -> Dict[str, Any]:
    """Return preprocessed forecast data for a model and time window."""
    empty = dict(
        x=np.array([]),
        y=np.array([]),
        width=np.array([]),
        height=np.array([]),
        log10_rate=np.array([]),
        mapper_meta=None,
    )

    if model_index is None or timewindow_str is None:
        return empty

    models = getattr(manifest, "models", []) or []
    if model_index < 0 or model_index >= len(models):
        return empty

    return load_gridded_forecast(manifest, model_index, timewindow_str)


def build_spatial_figure(manifest: Manifest, height: int = 350):
    """Create a basemap figure and an empty forecast overlay with colorbar."""
    region = getattr(manifest, "region", None)

    fig, *_ = build_region_basemap(
        region,
        basemap="WorldTerrain",
        min_height=height,
        plot_cells=False,
    )

    fig.output_backend = "webgl"

    source = ColumnDataSource(
        data=dict(
            x=[],
            y=[],
            width=[],
            height=[],
            log10_rate=[],
        )
    )

    palette = make_magma_alpha_palette(alpha_exp=0.7, alpha_0=None)
    color_mapper = LinearColorMapper(
        palette=palette,
        low=0.0,
        high=1.0,
        nan_color=(0, 0, 0, 0),
    )

    renderer = fig.rect(
        x="x",
        y="y",
        width="width",
        height="height",
        source=source,
        fill_color={"field": "log10_rate", "transform": color_mapper},
        fill_alpha=1.0,
        line_color=None,
        line_alpha=0.0,
    )

    hover = HoverTool(
        renderers=[renderer],
        tooltips=[
            ("log10 λ", "@log10_rate{0.00}"),
        ],
        mode="mouse",
    )
    fig.add_tools(hover)

    color_bar = ColorBar(
        color_mapper=color_mapper,
        label_standoff=8,
        location="bottom",
        orientation="horizontal",
        title="log10 λ",
        title_text_color="#e5e7eb",
        title_text_font_size="9pt",
        major_label_text_color="#e5e7eb",
        major_label_text_font_size="7pt",
        background_fill_color=None,
        background_fill_alpha=0.0,
        border_line_color=None,
    )
    fig.add_layout(color_bar, "below")

    fig._forecast_color_mapper = color_mapper

    return fig, source


def build_spatial_panel(
    manifest: Manifest,
    model_select: pn.widgets.Select,
    timewindow_select: pn.widgets.Select,
) -> pn.Column:
    """
    Build the spatial forecast panel with map and interactive color range.

    The model/timewindow selectors are provided by the caller and are typically
    displayed in the left metadata panel.
    """
    color_range = pn.widgets.RangeSlider(
        name="",
        start=-5.0,
        end=5.0,
        value=(-2.0, 2.0),
        step=0.1,
        show_value=False,
        sizing_mode="stretch_width",
    )

    fig, source = build_spatial_figure(manifest, height=350)
    fig_pane = pn.pane.Bokeh(fig, sizing_mode="stretch_both")

    def apply_color_range(event=None):
        color_mapper = getattr(fig, "_forecast_color_mapper", None)
        if color_mapper is None:
            return

        val = color_range.value
        if not val or len(val) != 2:
            return

        low, high = val
        if low is None or high is None or high <= low:
            return

        color_mapper.low = low
        color_mapper.high = high

    def update_forecast(event=None):
        model_idx = model_select.value
        tw_str = timewindow_select.value

        data = load_forecast_for_selection(manifest, model_idx, tw_str)
        default = dict(x=[], y=[], width=[], height=[], log10_rate=[], mapper_meta=None)
        default.update(data or {})

        source.data = {k: v for k, v in default.items() if k != "mapper_meta"}

        color_mapper = getattr(fig, "_forecast_color_mapper", None)
        mapper_meta = default.get("mapper_meta")

        if color_mapper is not None and mapper_meta is not None:
            vmin = mapper_meta["vmin"]
            vmax = mapper_meta["vmax"]

            global_low = _GLOBAL_FC_RANGE["low"]
            global_high = _GLOBAL_FC_RANGE["high"]

            if global_low is None or vmin < global_low:
                global_low = vmin
            if global_high is None or vmax > global_high:
                global_high = vmax

            _GLOBAL_FC_RANGE["low"] = global_low
            _GLOBAL_FC_RANGE["high"] = global_high

            color_range.start = global_low
            color_range.end = global_high

            initialized = _GLOBAL_FC_RANGE["initialized"]

            if not initialized:
                new_low, new_high = global_low, global_high
                _GLOBAL_FC_RANGE["initialized"] = True
            else:
                val_low, val_high = color_range.value

                val_low = max(global_low, min(val_low, global_high))
                val_high = max(global_low, min(val_high, global_high))

                if val_high <= val_low:
                    new_low, new_high = global_low, global_high
                else:
                    new_low, new_high = val_low, val_high

            color_range.value = (new_low, new_high)

    model_select.param.watch(update_forecast, "value")
    timewindow_select.param.watch(update_forecast, "value")
    color_range.param.watch(apply_color_range, "value")

    update_forecast()

    return pn.Column(
        fig_pane,
        color_range,
        sizing_mode="stretch_both",
    )


def forecast_overview_block(manifest: Manifest) -> pn.panel:
    """Return the title block for the Forecasts tab."""
    text = "## Forecasts"
    return pn.pane.Markdown(text, sizing_mode="stretch_width")


def forecast_metadata_section(manifest: Manifest) -> pn.panel:
    """
    Display forecast availability summary:
    - Total time windows
    - Per-model forecast count with a colored badge.
    """

    models = getattr(manifest, "models", []) or []
    time_windows = getattr(manifest, "time_windows", []) or []
    n_tw = len(time_windows)

    lines: List[str] = []
    lines.append("### Forecast Summary\n")
    lines.append(f"**Total Time Windows:** {n_tw}\n")

    if not models:
        lines.append("- _No models configured in manifest._")
        return pn.pane.Markdown("\n".join(lines), sizing_mode="stretch_width")

    for m in models:
        name = m.get("name", "Unnamed Model")
        fc_map = m.get("forecasts", {}) or {}

        n_available = sum(1 for tw in time_windows if fc_map.get(tw) is not None)

        if n_available == 0:
            color = "#ef4444"
        elif n_available < n_tw:
            color = "#f59e0b"
        else:
            color = "#22c55e"

        badge = f"<span style='color:{color}; font-size:14px;'>●</span>"
        lines.append(f"- {name}: {n_available}/{n_tw} {badge}")

    return pn.pane.Markdown(
        "\n".join(lines),
        sizing_mode="stretch_width",
        styles={"font-size": "11px"},
    )


def build_model_metadata_pane(
    manifest: Manifest,
    model_select: pn.widgets.Select,
) -> pn.pane.Markdown:
    """
    Build a small metadata block describing the currently selected model.

    This is updated whenever the model_select widget changes.
    """
    models = getattr(manifest, "models", []) or []
    time_windows = getattr(manifest, "time_windows", []) or []

    pane = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
        styles={"font-size": "11px"},
    )

    def _update(event=None):
        idx = model_select.value
        if idx is None or not models or idx < 0 or idx >= len(models):
            pane.object = "_No model selected._"
            return

        m = models[idx]
        name = m.get("name", f"Model {idx+1}")

        model_class = (
            "Gridded Forecast"
            if m.get("forecast_class") == "GriddedForecastRepository"
            else "Catalog Forecast"
        )

        unit = m.get("forecast_unit", "—")
        giturl = m.get("giturl") or None
        doi = m.get("doi") or None
        fc_map = m.get("forecasts", {}) or {}
        fmt = m.get("fmt", None)
        n_tw_total = len(time_windows)
        n_avail = sum(1 for tw in time_windows if fc_map.get(tw) is not None)

        lines: List[str] = []
        lines.append("### Selected Model\n")
        lines.append(f"- **Name:** {name}")
        lines.append(f"- **Forecast Type:** {model_class}")
        lines.append(f"- **Forecast unit:** {unit}")
        if giturl:
            lines.append(f"- **Source repo:** {giturl}")
        if doi:
            badge = make_doi_badge(doi)
            lines.append(f"- **DOI:** {badge}")
        if fmt:
            lines.append(f"- **Format:** {fmt}")

        badge = f"<span style='color: #22c55e; font-size:14px;'>●</span>"
        lines.append(f"- **Forecast coverage:** {n_avail}/{n_tw_total} time windows {badge}")

        pane.object = "\n".join(lines)

    # Initial fill + watcher
    _update()
    model_select.param.watch(_update, "value")

    return pane


def build_metadata_panel(
    manifest: Manifest,
    model_select: pn.widgets.Select,
    timewindow_select: pn.widgets.Select,
) -> pn.Column:
    """Build the left-side metadata panel for the Forecasts tab."""
    overview = forecast_overview_block(manifest)

    model_metadata = build_model_metadata_pane(manifest, model_select)

    summary_metadata = forecast_metadata_section(manifest)

    summary = pn.Accordion(
        ("Summary", summary_metadata),
        sizing_mode="stretch_width",
        active_header_background="#0b1120",
        header_background="#0b1120",
        header_color="#e5e7eb",
        styles={"stroke": "#e5e7eb"},
    )

    return pn.Column(
        overview,
        pn.layout.Divider(),
        summary,
        pn.layout.Divider(),
        model_select,
        timewindow_select,
        model_metadata,
        width=380,
    )


def build_forecasts_view(manifest: Manifest) -> pn.layout.Panel:
    """Build the Forecasts tab view."""

    model_options = build_model_options(manifest)
    tw_options = build_timewindow_options(manifest)

    model_select = pn.widgets.Select(
        name="",
        options=model_options,
        sizing_mode="stretch_width",
    )
    timewindow_select = pn.widgets.Select(
        name="",
        options=tw_options,
        sizing_mode="stretch_width",
    )

    left = build_metadata_panel(manifest, model_select, timewindow_select)

    spatial_panel = build_spatial_panel(manifest, model_select, timewindow_select)
    spatial_panel.sizing_mode = "stretch_both"

    return pn.Row(
        left,
        pn.Spacer(width=25),
        spatial_panel,
        sizing_mode="stretch_both",
    )
