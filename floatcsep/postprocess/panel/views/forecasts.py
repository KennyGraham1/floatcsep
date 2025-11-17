# views/forecasts.py

from typing import Dict, Any, Optional, List

import panel as pn
from bokeh.models import ColumnDataSource, HoverTool

from ..manifest import Manifest
from .utils import build_region_basemap  # same helper as in cats.py

pn.extension()


# ---------------------------------------------------------------------------
# Helpers for select options
# ---------------------------------------------------------------------------


def _build_model_options(manifest: Manifest) -> Dict[str, int]:
    """Return label -> model_index mapping for the Model select widget."""
    options: Dict[str, int] = {}
    models: List[Dict[str, Any]] = getattr(manifest, "models", []) or []
    for i, model in enumerate(models):
        name = model.get("name") or f"Model {i+1}"
        unit = model.get("forecast_unit")
        if unit:
            label = f"{name} ({unit})"
        else:
            label = name
        options[label] = i
    return options


def _build_timewindow_options(manifest: Manifest) -> Dict[str, str]:
    """Return label -> timewindow_str mapping for the Time Window select."""
    tw_strings: List[str] = getattr(manifest, "time_windows", []) or []
    options: Dict[str, str] = {}
    for i, tw in enumerate(tw_strings, start=1):
        label = f"T{i}: {tw}"
        options[label] = tw
    return options


# ---------------------------------------------------------------------------
# Forecast data loader (placeholder)
# ---------------------------------------------------------------------------


def _load_forecast_for_selection(
    manifest: Manifest,
    model_index: Optional[int],
    timewindow_str: Optional[str],
) -> Dict[str, Any]:
    """
    Placeholder for loading a forecast grid for a given model + time window.

    Later, this should:
      - Use manifest.models[model_index]["repository"] / ["registry"]
      - Retrieve a CSEPGrid-like forecast object
      - Convert lon/lat centers to WebMercator x, y
      - Map values -> colors/alphas

    For now, return an empty structure so the layout is correct but lightweight.
    """
    if model_index is None or timewindow_str is None:
        return dict(x=[], y=[], value=[], color=[], alpha=[])

    # TODO: implement real loading logic
    return dict(x=[], y=[], value=[], color=[], alpha=[])


# ---------------------------------------------------------------------------
# Basemap + CDS (single figure instance)
# ---------------------------------------------------------------------------


def _build_forecast_spatial_figure(manifest: Manifest, height: int = 350):
    """Create a basemap figure and an empty forecast overlay."""
    region = getattr(manifest, "region", None)

    # Same style as _build_spatial_catalog_figure
    fig = build_region_basemap(
        region,
        basemap="WorldTerrain",
        min_height=height,
        plot_cells=False,
    )

    source = ColumnDataSource(
        data=dict(
            x=[],
            y=[],
            value=[],
            color=[],
            alpha=[],
        )
    )

    renderer = fig.circle(
        x="x",
        y="y",
        source=source,
        size=5,
        fill_color="color",
        fill_alpha="alpha",
        line_color=None,
    )

    hover = HoverTool(
        renderers=[renderer],
        tooltips=[
            ("Forecast", "@value"),
            ("x", "@x{0.00}"),
            ("y", "@y{0.00}"),
        ],
        mode="mouse",
    )
    fig.add_tools(hover)

    return fig, source


def _build_spatial_forecast_panel(manifest: Manifest) -> pn.Column:
    """
    Build the spatial forecast panel:

    - Top: Model + Time Window selects
    - Middle: basemap with forecast overlay
    - Bottom: small status markdown

    Sizing is aligned with _build_spatial_catalog_panel:
      - Inner Bokeh pane uses sizing_mode="stretch_width"
      - This Column uses sizing_mode="stretch_width"
      - Container (Row/Tabs) controls vertical stretching
    """
    model_options = _build_model_options(manifest)
    tw_options = _build_timewindow_options(manifest)

    model_select = pn.widgets.Select(
        name="Model",
        options=model_options,
        sizing_mode="stretch_width",
    )
    timewindow_select = pn.widgets.Select(
        name="Time window",
        options=tw_options,
        sizing_mode="stretch_width",
    )

    fig, source = _build_forecast_spatial_figure(manifest, height=350)
    fig_pane = pn.pane.Bokeh(fig, sizing_mode="stretch_width")

    status_md = pn.pane.Markdown(
        "_Select a **model** and **time window** to view a forecast overlay._",
        sizing_mode="stretch_width",
        styles={"font-size": "10px", "opacity": 0.85},
        margin=(4, 0, 0, 0),
    )

    def _update_forecast(event=None):
        model_idx = model_select.value
        tw_str = timewindow_select.value

        data = _load_forecast_for_selection(manifest, model_idx, tw_str)
        default = dict(x=[], y=[], value=[], color=[], alpha=[])
        default.update(data or {})
        source.data = default

        if model_idx is None or tw_str is None:
            status_md.object = (
                "_Select a **model** and **time window** to view a forecast overlay._"
            )
            return

        models = getattr(manifest, "models", []) or []
        if model_idx < 0 or model_idx >= len(models):
            status_md.object = "_Invalid model index in selection._"
            return

        model_cfg = models[model_idx]
        name = model_cfg.get("name") or f"Model {model_idx+1}"
        status_md.object = (
            f"Showing forecast **placeholder** for:\n\n"
            f"- **Model:** `{name}`\n"
            f"- **Time window:** `{tw_str}`\n\n"
            "_Once the loader is implemented, this will display the actual forecast grid._"
        )

    model_select.param.watch(_update_forecast, "value")
    timewindow_select.param.watch(_update_forecast, "value")

    _update_forecast()

    controls_row = pn.Row(
        model_select,
        timewindow_select,
        sizing_mode="stretch_width",
    )

    return pn.Column(
        controls_row,
        fig_pane,
        status_md,
        sizing_mode="stretch_width",
    )


# ---------------------------------------------------------------------------
# Left-side metadata panel (mirrors Catalogs)
# ---------------------------------------------------------------------------


def _forecast_overview_block(manifest: Manifest) -> pn.panel:
    text = "## Forecasts"
    return pn.pane.Markdown(text, sizing_mode="stretch_width")


def _forecast_metadata_section(manifest: Manifest) -> pn.panel:
    """Very lightweight metadata: general info about models."""
    lines: List[str] = ["### Models"]

    models: List[Dict[str, Any]] = getattr(manifest, "models", []) or []
    if not models:
        lines.append("- _No models configured in manifest._")
    else:
        for i, m in enumerate(models, start=1):
            name = m.get("name") or f"Model {i}"
            unit = m.get("forecast_unit") or "?"
            path = m.get("path") or "?"
            lines.append(f"- **{name}** – unit: `{unit}`, path: `{path}`")

    return pn.pane.Markdown(
        "\n".join(lines),
        sizing_mode="stretch_width",
        styles={"font-size": "11px"},
    )


def _build_metadata_panel(manifest: Manifest) -> pn.Column:
    """Left-side metadata panel for Forecasts, aligned with Catalogs."""
    overview = _forecast_overview_block(manifest)
    metadata = _forecast_metadata_section(manifest)

    return pn.Column(
        overview,
        pn.layout.Divider(),
        metadata,
        width=380,  # same as _build_metadata_panel in cats.py
    )


# ---------------------------------------------------------------------------
# Entry point: build_forecasts_view
# ---------------------------------------------------------------------------


def build_forecasts_view(manifest: Manifest) -> pn.layout.Panel:
    """
    Build the Forecasts tab view.

    Layout is consistent with build_catalogs_view:
      - Left: metadata (fixed width)
      - Spacer: 25 px
      - Right: plots panel controlling vertical stretch
    """
    left = _build_metadata_panel(manifest)

    spatial_panel = _build_spatial_forecast_panel(manifest)
    spatial_panel.sizing_mode = "stretch_both"

    return pn.Row(
        left,
        pn.Spacer(width=25),
        spatial_panel,
        sizing_mode="stretch_both",
    )
