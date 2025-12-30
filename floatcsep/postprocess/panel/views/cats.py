import json
from datetime import datetime, date, timezone
from pathlib import Path

import numpy as np
import panel as pn
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    DatetimeTickFormatter,
    Range1d,
    LabelSet,
)
from bokeh.plotting import figure

from ..manifest import Manifest
from .utils import (
    build_region_basemap,
    lonlat_to_mercator,
    parse_time_window_strings,
    make_doi_badge,
)
from floatcsep.utils.file_io import CatalogParser


def _to_datetime_or_none(value):
    """Return value as timezone-aware datetime or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            dtime = datetime.fromisoformat(value)
            return dtime.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


SUBSCRIPT_DIGITS = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def _make_window_label(i: int) -> str:
    """Return a time-window label like for index i."""
    idx = str(i + 1).translate(SUBSCRIPT_DIGITS)
    return f"T{idx}"


def _compute_marker_sizes(
    mags: np.ndarray,
    min_size: float = 5.0,
    max_size: float = 18.0,
    power: float = 2.5,
) -> np.ndarray:
    """Map magnitudes to Bokeh marker sizes."""
    mags = np.asarray(mags, dtype=float)
    if mags.size == 0 or not np.isfinite(mags).any():
        return np.array([], dtype=float)

    vmin = np.nanmin(mags)
    vmax = np.nanmax(mags)
    if not np.isfinite(vmin) or not np.isfinite(vmax) or vmax <= vmin:
        return np.full(mags.shape, (min_size + max_size) / 2.0, dtype=float)

    norm = ((mags - vmin) / (vmax - vmin)) ** power
    return min_size + norm * (max_size - min_size)


def _fmt_dt(dt):
    """Format datetime to second precision."""
    if dt is None:
        return None
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _load_csep_catalog_from_manifest(manifest: Manifest):
    """Load a CSEPCatalog from manifest.catalog['path']."""
    cat_info = getattr(manifest, "catalog", None)
    if not isinstance(cat_info, dict):
        return None

    path = cat_info.get("path")
    if not path:
        return None

    app_root = Path(getattr(manifest, "app_root", "."))
    path_obj = Path(path)

    if not path_obj.is_absolute():
        path_obj = (app_root / path_obj).resolve()
    else:
        path_obj = path_obj.resolve()

    try:
        if path_obj.suffix.lower() == ".json":
            try:
                return CatalogParser.json(str(path_obj))
            except json.JSONDecodeError:
                return CatalogParser.ascii(str(path_obj))
        else:
            return CatalogParser.ascii(str(path_obj))
    except FileNotFoundError:
        return None
    except Exception:
        return None


def _build_spatial_catalog_legend(catalog) -> pn.pane.Markdown:
    """Return a small static legend for the spatial catalog scatter."""
    if catalog is None or catalog.event_count == 0:
        text = "_No catalog loaded; legend unavailable._"
        return pn.pane.Markdown(text, sizing_mode="stretch_width", styles={"font-size": "9px"})

    mags = catalog.get_magnitudes()
    min_mag = float(np.nanmin(mags))
    max_mag = float(np.nanmax(mags))

    mags_ticks = np.linspace(min_mag, max_mag, 4)
    mags_ticks = np.round(mags_ticks, 1)

    sizes = _compute_marker_sizes(mags_ticks, min_size=5.0, max_size=18.0, power=2.5)
    font_min, font_max = 9, 15
    smin, smax = sizes.min(), sizes.max()
    if smax > smin:
        font_sizes = font_min + (sizes - smin) / (smax - smin) * (font_max - font_min)
    else:
        font_sizes = np.full_like(sizes, (font_min + font_max) / 2.0)

    bullet_parts = []
    for m, fs in zip(mags_ticks, font_sizes):
        bullet_parts.append(f'<span style="font-size:{fs:.1f}px;">●</span> M {m:g}')
    bullets_html = " &nbsp;&nbsp; ".join(bullet_parts)

    legend_html = f"""
<span style="font-size:10px; opacity:0.8;">
<b>Magnitude legend:</b> {bullets_html}<br/>
<b>Colors:</b> <span style="color:#38bdf8;">●</span> Input Catalog (t &lt; start) &nbsp;&nbsp;
<span style="color:#ef4444;">●</span> Test Catalog (start &lt; t)
</span>
"""

    return pn.pane.Markdown(
        legend_html,
        sizing_mode="stretch_width",
        styles={"font-size": "10px"},
        margin=(4, 0, 0, 0),
    )


def _build_spatial_catalog_figure(manifest: Manifest, height: int = 350):
    """Build spatial catalog figure on a basemap."""
    region = getattr(manifest, "region", None)
    catalog = _load_csep_catalog_from_manifest(manifest)

    fig, *_ = build_region_basemap(
        region, basemap="WorldTerrain", min_height=height, plot_cells=False
    )

    if catalog is None or catalog.event_count == 0:
        source = ColumnDataSource(
            data={
                "x": [],
                "y": [],
                "mag": [],
                "size": [],
                "time_str": [],
                "event_id": [],
                "color": [],
                "category": [],
            }
        )
        fig.circle(
            x="x",
            y="y",
            source=source,
            size="size",
            fill_color="color",
            fill_alpha=0.0,
            line_alpha=0.0,
        )
        return fig, source

    start_date = _to_datetime_or_none(getattr(manifest, "start_date", None))
    end_date = _to_datetime_or_none(getattr(manifest, "end_date", None))

    lons = catalog.get_longitudes()
    lats = catalog.get_latitudes()
    mags = catalog.get_magnitudes()
    dts = catalog.get_datetimes()
    event_ids_raw = catalog.get_event_ids()

    indices = list(range(len(dts)))
    if end_date is not None:
        indices = [i for i in indices if dts[i] <= end_date]

    if not indices:
        source = ColumnDataSource(
            data={
                "x": [],
                "y": [],
                "mag": [],
                "size": [],
                "time_str": [],
                "event_id": [],
                "color": [],
                "category": [],
            }
        )
        fig.circle(
            x="x",
            y="y",
            source=source,
            size="size",
            fill_color="color",
            fill_alpha=0.0,
            line_alpha=0.0,
        )
        return fig, source

    input_idx = []
    test_idx = []
    for i in indices:
        dt = dts[i]
        if start_date is not None and dt < start_date:
            input_idx.append(i)
        else:
            test_idx.append(i)

    ordered_indices = input_idx + test_idx

    lons = np.asarray(lons)[ordered_indices]
    lats = np.asarray(lats)[ordered_indices]
    mags = np.asarray(mags)[ordered_indices]
    dts_ordered = [dts[i] for i in ordered_indices]
    event_ids_ordered = [event_ids_raw[i] for i in ordered_indices]

    x, y = lonlat_to_mercator(lons, lats)

    event_ids = [
        eid.decode("utf-8") if isinstance(eid, (bytes, bytearray)) else str(eid)
        for eid in event_ids_ordered
    ]
    time_str = [dt.strftime("%Y-%m-%d %H:%M:%S") for dt in dts_ordered]

    sizes = _compute_marker_sizes(mags, min_size=3.0, max_size=18.0, power=3)

    INPUT_COLOR = "#38bdf8"
    TEST_COLOR = "#ef4444"

    colors = []
    categories = []
    alphas = []
    for dt in dts_ordered:
        if start_date is not None and dt < start_date:
            colors.append(INPUT_COLOR)
            categories.append("input")
            alphas.append(0.35)
        else:
            colors.append(TEST_COLOR)
            categories.append("test")
            alphas.append(0.6)

    source = ColumnDataSource(
        data={
            "x": x,
            "y": y,
            "mag": mags,
            "size": sizes,
            "time_str": time_str,
            "event_id": event_ids,
            "color": colors,
            "category": categories,
            "alphas": alphas,
        }
    )

    fig.circle(
        x="x",
        y="y",
        source=source,
        size="size",
        fill_color="color",
        fill_alpha="alphas",
        line_color="#020617",
        line_width=0.4,
        line_alpha=0.5,
    )

    hover = HoverTool(
        tooltips=[
            ("Time", "@time_str"),
            ("Magnitude", "@mag{0.00}"),
            ("ID", "@event_id"),
        ],
        mode="mouse",
    )
    fig.add_tools(hover)

    return fig, source


def _build_spatial_catalog_panel(manifest: Manifest) -> pn.panel:
    """Build the spatial catalog panel."""
    catalog = _load_csep_catalog_from_manifest(manifest)
    fig, _source = _build_spatial_catalog_figure(manifest, height=350)
    legend_md = _build_spatial_catalog_legend(catalog)

    return pn.Column(
        pn.pane.Bokeh(fig, sizing_mode="stretch_width"),
        legend_md,
        sizing_mode="stretch_both",
    )


def _build_magtime_catalog_figure(manifest: Manifest, height: int = 220):
    """Build magnitude–time scatter with embedded time windows."""
    catalog = _load_csep_catalog_from_manifest(manifest)

    if catalog is None or catalog.event_count == 0:
        fig = figure(
            x_axis_type="datetime",
            height=height,
            sizing_mode="stretch_width",
            toolbar_location="above",
            tools="xwheel_zoom,xpan,box_zoom,reset",
            active_scroll="xwheel_zoom",
        )
        fig.title.text = "No catalog events"
        fig.yaxis.axis_label = "Magnitude"
        fig.xaxis.axis_label = "Time"

        fig.background_fill_color = "#0b1120"
        fig.border_fill_color = "#0b1120"
        fig.outline_line_color = None
        fig.grid.grid_line_color = "#1f2933"
        fig.axis.major_label_text_color = "#e5e7eb"
        fig.axis.axis_line_color = "#6b7280"
        fig.axis.major_tick_line_color = "#6b7280"
        fig.axis.minor_tick_line_color = None

        return fig, ColumnDataSource({"time": [], "mag": []})

    start_date = _to_datetime_or_none(getattr(manifest, "start_date", None))
    end_date = _to_datetime_or_none(getattr(manifest, "end_date", None))

    dts = catalog.get_datetimes()
    mags = np.asarray(catalog.get_magnitudes(), dtype=float)
    event_ids_raw = catalog.get_event_ids()

    indices = list(range(len(dts)))
    if end_date is not None:
        indices = [i for i in indices if dts[i] <= end_date]

    if not indices:
        fig = figure(
            x_axis_type="datetime",
            height=height,
            sizing_mode="stretch_width",
            toolbar_location="above",
            tools="xwheel_zoom,xpan,box_zoom,reset",
            active_scroll="xwheel_zoom",
        )
        fig.title.text = "No events within experiment end time"
        fig.yaxis.axis_label = "Magnitude"
        fig.xaxis.axis_label = "Time"
        fig.background_fill_color = "#0b1120"
        fig.border_fill_color = "#0b1120"
        fig.outline_line_color = None
        fig.grid.grid_line_color = "#1f2933"
        fig.axis.major_label_text_color = "#e5e7eb"
        fig.axis.axis_line_color = "#6b7280"
        fig.axis.major_tick_line_color = "#6b7280"
        fig.axis.minor_tick_line_color = None

        return fig, ColumnDataSource({"time": [], "mag": []})

    input_idx = []
    test_idx = []
    for i in indices:
        dt = dts[i]
        if start_date is not None and dt < start_date:
            input_idx.append(i)
        else:
            test_idx.append(i)

    ordered_indices = input_idx + test_idx

    dts_ordered = [dts[i] for i in ordered_indices]
    mags_ordered = mags[ordered_indices]
    event_ids_ordered = [event_ids_raw[i] for i in ordered_indices]

    sizes = _compute_marker_sizes(mags_ordered, min_size=4.0, max_size=16.0, power=3.0)

    INPUT_COLOR = "#38bdf8"
    TEST_COLOR = "#ef4444"

    colors = []
    alphas = []
    categories = []
    for dt in dts_ordered:
        if start_date is not None and dt < start_date:
            colors.append(INPUT_COLOR)
            categories.append("input")
            alphas.append(0.35)
        else:
            colors.append(TEST_COLOR)
            categories.append("test")
            alphas.append(0.65)

    time_str = [dt.strftime("%Y-%m-%d %H:%M:%S") for dt in dts_ordered]
    event_ids = [
        eid.decode("utf-8") if isinstance(eid, (bytes, bytearray)) else str(eid)
        for eid in event_ids_ordered
    ]

    source = ColumnDataSource(
        data={
            "time": dts_ordered,
            "mag": mags_ordered,
            "size": sizes,
            "color": colors,
            "alphas": alphas,
            "category": categories,
            "time_str": time_str,
            "event_id": event_ids,
        }
    )

    fig = figure(
        x_axis_type="datetime",
        height=height,
        sizing_mode="stretch_width",
        toolbar_location="above",
        tools="xwheel_zoom,xpan,box_zoom,reset",
        active_scroll="xwheel_zoom",
    )

    y_min = float(np.nanmin(mags_ordered))
    y_max = float(np.nanmax(mags_ordered))
    y_max_pad = max(0.4, 0.2 * (y_max - y_min) if y_max > y_min else 0.0)
    y_min_pad = 0.15
    fig.y_range = Range1d(y_min - y_min_pad, y_max + y_max_pad)

    t_min = min(dts_ordered)
    t_max = max(dts_ordered)
    if t_max > t_min:
        pad = (t_max - t_min) * 0.05
        fig.x_range = Range1d(t_min - pad, t_max + pad)

    tw_strings = getattr(manifest, "time_windows", None) or []
    parsed_raw = parse_time_window_strings(tw_strings)

    if parsed_raw:
        windows_sorted = sorted(parsed_raw, key=lambda tw: tw["start"])

        lane_last_end = []
        lanes = []

        for tw in windows_sorted:
            start = tw["start"]
            end = tw["end"]
            assigned = False
            for i, last_end in enumerate(lane_last_end):
                if start >= last_end:
                    lane_last_end[i] = end
                    lanes.append(i)
                    assigned = True
                    break
            if not assigned:
                lane_last_end.append(end)
                lanes.append(len(lane_last_end) - 1)

        n_lanes = max(lanes) + 1 if lanes else 1

        y_top_min = y_max
        y_top_max = y_max + y_max_pad
        lane_step = (y_top_max - y_top_min) / max(n_lanes, 1)
        bar_height = lane_step * 0.7

        left = []
        right = []
        bottom = []
        top = []
        labels = []
        start_strs = []
        end_strs = []
        length_days = []
        y_label = []

        for i, tw in enumerate(windows_sorted):
            lane = lanes[i]

            lane_center = y_top_min + (lane + 0.5) * lane_step
            b = lane_center - bar_height / 2.0
            t = lane_center + bar_height / 2.0

            left.append(tw["start"])
            right.append(tw["end"])
            bottom.append(b)
            top.append(t)
            labels.append(_make_window_label(i))
            start_strs.append(tw["start_str"])
            end_strs.append(tw["end_str"])
            length_days.append(tw["length_days"])
            y_label.append(lane_center)

        tw_source = ColumnDataSource(
            data={
                "start": left,
                "end": right,
                "bottom": bottom,
                "top": top,
                "label": labels,
                "start_str": start_strs,
                "end_str": end_strs,
                "length_days": length_days,
                "y_label": y_label,
            }
        )

        window_renderer = fig.quad(
            left="start",
            right="end",
            bottom="bottom",
            top="top",
            source=tw_source,
            fill_color="#38bdf8",
            fill_alpha=0.16,
            line_color=None,
        )

        labels_glyph = LabelSet(
            x="start",
            y="y_label",
            text="label",
            source=tw_source,
            text_font_size="7pt",
            text_color="#e5e7eb",
            text_align="left",
            text_baseline="middle",
            background_fill_color="#020617",
            background_fill_alpha=0.0,
            border_line_color=None,
        )
        fig.add_layout(labels_glyph)

        window_hover = HoverTool(
            renderers=[window_renderer],
            tooltips=[
                ("Start", "@start_str"),
                ("End", "@end_str"),
                ("Length (days)", "@length_days"),
            ],
            mode="mouse",
        )
        fig.add_tools(window_hover)

    scatter_renderer = fig.circle(
        x="time",
        y="mag",
        source=source,
        size="size",
        fill_color="color",
        fill_alpha="alphas",
        line_color="#020617",
        line_width=0.4,
        line_alpha=0.6,
    )

    fig.yaxis.axis_label = "Magnitude"
    fig.xaxis.axis_label = "Time"

    fig.background_fill_color = "#0b1120"
    fig.border_fill_color = "#0b1120"
    fig.outline_line_color = None
    fig.grid.grid_line_color = "#1f2933"
    fig.axis.major_label_text_color = "#e5e7eb"
    fig.axis.axis_line_color = "#6b7280"
    fig.axis.major_tick_line_color = "#6b7280"
    fig.axis.minor_tick_line_color = None

    fig.xaxis.formatter = DatetimeTickFormatter(
        years="%Y",
        months="%b %Y",
        days="%d %b %Y",
        hours="%d %b %Y",
    )
    fig.xaxis.major_label_orientation = np.pi / 2
    fig.xaxis.major_label_text_font_size = "7pt"
    fig.yaxis.major_label_text_font_size = "8pt"

    event_hover = HoverTool(
        renderers=[scatter_renderer],
        tooltips=[
            ("Time", "@time_str"),
            ("Magnitude", "@mag{0.00}"),
            ("ID", "@event_id"),
        ],
        mode="mouse",
    )
    fig.add_tools(event_hover)

    return fig, source


def _build_magtime_catalog_panel(manifest: Manifest) -> pn.panel:
    """Build the magnitude–time catalog panel."""
    magtime_fig, _source = _build_magtime_catalog_figure(manifest, height=280)
    magtime_pane = pn.pane.Bokeh(magtime_fig, sizing_mode="stretch_width")

    return pn.Column(
        magtime_pane,
        sizing_mode="stretch_width",
    )


def _build_plots_panel(manifest: Manifest) -> pn.Tabs:
    """Build tabs with spatial and magnitude–time plots."""
    spatial_panel = _build_spatial_catalog_panel(manifest)
    magtime_panel = _build_magtime_catalog_panel(manifest)

    return pn.Tabs(
        ("Spatial", spatial_panel),
        ("Magnitude–Time", magtime_panel),
        sizing_mode="stretch_both",
    )


def _catalog_overview_block(manifest: Manifest) -> pn.panel:
    """Build the title block for the Catalogs tab."""
    text = "## Catalogs"
    return pn.pane.Markdown(text, sizing_mode="stretch_width")


def _catalog_metadata_section(manifest: Manifest) -> pn.panel:
    """Build catalog metadata section from CSEPCatalog attributes."""
    cat_info = getattr(manifest, "catalog", None)
    cat_path = None
    if isinstance(cat_info, dict):
        cat_path = cat_info.get("path")

    csep_cat = _load_csep_catalog_from_manifest(manifest)

    lines = ["### Metadata"]

    if cat_path:
        lines.append(f"- **Path:** `{cat_path}`")

    if csep_cat is None:
        lines.append("")
        lines.append("_Catalog could not be loaded from this path._")
        return pn.pane.Markdown(
            "\n".join(lines),
            sizing_mode="stretch_width",
            styles={"font-size": "11px"},
        )

    name = getattr(csep_cat, "name", None)
    if not name and cat_path:
        name = Path(cat_path).name

    if name != cat_path:
        lines.append(f"- **Name:** {name}")

    provider = getattr(manifest, "catalog_provided", None)
    if provider:
        lines.append(f"- **Provider:** `{provider}`")

    lines.append(f"- **Event count:** {csep_cat.event_count}")

    start_time = getattr(csep_cat, "start_time", None)
    end_time = getattr(csep_cat, "end_time", None)

    start_str = _fmt_dt(start_time)
    end_str = _fmt_dt(end_time)
    if start_time and end_time:
        lines.append(f"- **Time span:** {start_str} → {end_str}")

    min_mag = getattr(csep_cat, "min_magnitude", None)
    max_mag = getattr(csep_cat, "max_magnitude", None)
    if min_mag is not None and max_mag is not None:
        lines.append(f"- **Magnitude range:** [{min_mag:.2f}, {max_mag:.2f}]")

    try:
        depths = csep_cat.get_depths()
        if depths is not None and len(depths) > 0:
            min_depth = float(np.nanmin(depths))
            max_depth = float(np.nanmax(depths))
            lines.append(f"- **Depth range:** [{min_depth:.1f}, {max_depth:.1f}] km")
    except Exception:
        pass

    try:
        lon_min, lon_max, lat_min, lat_max = csep_cat.get_bbox()
        lines.append(
            "- **Catalog extent:** "
            f"lon [{lon_min:.2f}, {lon_max:.2f}], "
            f"lat [{lat_min:.2f}, {lat_max:.2f}]"
        )
    except Exception:
        pass

    region = getattr(csep_cat, "region", None)
    region_name = getattr(region, "name", None) if region is not None else None
    if region_name:
        lines.append(f"- **Region (catalog):** {region_name}")

    filters = getattr(csep_cat, "filters", None)
    if filters:
        lines.append(f"- **Filters:** `{filters}`")
    # Experiment DOI (e.g. Zenodo for the experiment bundle)
    doi = getattr(manifest, "catalog_doi", None)
    if doi:
        badge = make_doi_badge(doi)
        lines.append(f"- **DOI:** {badge}")

    date_accessed = getattr(csep_cat, "date_accessed", None)
    if date_accessed:
        lines.append(f"- **Date accessed:** {_fmt_dt(date_accessed)}")

    return pn.pane.Markdown(
        "\n".join(lines),
        sizing_mode="stretch_width",
        styles={"font-size": "11px"},
    )


def _build_metadata_panel(manifest: Manifest) -> pn.Column:
    """Build right-side catalog metadata panel."""
    overview = _catalog_overview_block(manifest)
    metadata = _catalog_metadata_section(manifest)

    return pn.Column(
        overview,
        pn.layout.Divider(),
        metadata,
        width=380,
    )


def build_catalogs_view(manifest: Manifest) -> pn.layout.Panel:
    """Build the Catalogs tab view."""
    left = _build_metadata_panel(manifest)
    right = _build_plots_panel(manifest)

    return pn.Row(
        left,
        pn.Spacer(width=25),
        right,
        sizing_mode="stretch_both",
    )
