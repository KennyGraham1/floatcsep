from typing import Optional

import numpy as np
from datetime import datetime, timedelta

import xyzservices.providers as xyz
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    Range1d,
    Span,
    DatetimeTickFormatter,
)
from bokeh.plotting import figure
from shapely.geometry import Polygon, LineString, LinearRing, MultiLineString
from shapely.ops import unary_union


def make_doi_badge(doi: str, height: int = 14) -> str:
    """Return an inline HTML <a><img> snippet for a Zenodo-style DOI badge."""
    doi = doi.strip()
    return (
        f'<a href="https://doi.org/{doi}" target="_blank" rel="noopener noreferrer">'
        f'<img src="https://zenodo.org/badge/DOI/{doi}.svg" '
        f'alt="DOI" style="height:{height}px;vertical-align:middle;">'
        f"</a>"
    )


def fmt_coord(x: Optional[float], ndigits: int = 3) -> str:
    """Format a coordinate with sensible precision and no trailing zeros."""
    if x is None:
        return "?"
    try:
        s = f"{round(float(x), ndigits):.{ndigits}f}"
        s = s.rstrip("0").rstrip(".")
        return s
    except Exception:
        return str(x)


def lonlat_to_mercator(lon, lat):
    """Convert lon/lat in degrees to Web Mercator x/y in meters."""
    k = 6378137.0
    lon_rad = np.radians(lon)
    lat_rad = np.radians(lat)
    x = k * lon_rad
    y = k * np.log(np.tan(np.pi / 4.0 + lat_rad / 2.0))
    return x, y


def add_region_cells(fig, region, to_mercator=True, alpha=0.2):
    """Draw grid cells as semi-transparent patches."""
    xs_all = []
    ys_all = []

    for cell in region.polygons:
        pts = np.asarray(cell.points)
        xs, ys = pts[:, 0], pts[:, 1]
        if to_mercator:
            xs, ys = lonlat_to_mercator(xs, ys)
        xs_all.append(xs)
        ys_all.append(ys)

    fig.patches(
        xs=xs_all,
        ys=ys_all,
        fill_alpha=alpha,
        fill_color="#0077b6",
        line_color="#0077b6",
        line_alpha=0.24,
        line_width=0.2,
    )


def add_region_outline(
    fig,
    region,
    to_mercator=True,
    line_color="#0077b6",
    line_width=1.0,
    precision=4,
):
    """Draw outline of a CartesianGrid2D region, including holes."""
    cell_polys = [Polygon(np.round(cell.points, precision)) for cell in region.polygons]
    merged = unary_union(cell_polys)
    boundary = merged.boundary

    if isinstance(boundary, (LineString, LinearRing)):
        lines = [boundary]
    elif isinstance(boundary, MultiLineString):
        lines = list(boundary.geoms)
    else:
        return

    xs_list = []
    ys_list = []

    for line in lines:
        coords = np.asarray(line.coords)
        xs = coords[:, 0]
        ys = coords[:, 1]
        if to_mercator:
            xs, ys = lonlat_to_mercator(xs, ys)
        xs_list.append(xs)
        ys_list.append(ys)

    fig.multi_line(xs=xs_list, ys=ys_list, line_color=line_color, line_width=line_width)


def build_region_basemap(region, basemap="WorldTerrain", min_height=300, plot_cells=True):
    """Create a Bokeh figure with a dark basemap and optional region overlay."""
    if region is not None:
        xmin, xmax, ymin, ymax = region.get_bbox()
        pad_x = pad_y = 10 * region.dh
        xmin_p, xmax_p = xmin - pad_x, xmax + pad_x
        ymin_p, ymax_p = ymin - pad_y, ymax + pad_y

        x0, y0 = lonlat_to_mercator(xmin_p, ymin_p)
        x1, y1 = lonlat_to_mercator(xmax_p, ymax_p)
        x_range = (x0, x1)
        y_range = (y0, y1)
    else:
        x_range = (-18_000_000, 18_000_000)
        y_range = (-7_000_000, 7_000_000)

    fig = figure(
        x_range=x_range,
        y_range=y_range,
        x_axis_type="mercator",
        y_axis_type="mercator",
        tools="pan,wheel_zoom,box_zoom,reset",
        active_scroll="wheel_zoom",
        active_drag="pan",
        toolbar_location="right",
        match_aspect=True,
        sizing_mode="scale_width",
        min_width=300,
        min_height=min_height,
    )

    DARK_BASEMAPS = {
        "AlidadeSmoothDark": xyz.Stadia.AlidadeSmoothDark,
        "DarkMatter": xyz.CartoDB.DarkMatter,
        "WorldImagery": xyz.Esri.WorldImagery,
        "WorldTerrain": xyz.Esri.WorldTerrain,
        "WorldShadedRelief": xyz.Esri.WorldShadedRelief,
        "USImagery": xyz.USGS.USImagery,
        "BlueMarble": xyz.NASAGIBS.BlueMarble,
        "GDEM": xyz.NASAGIBS.ASTER_GDEM_Greyscale_Shaded_Relief,
    }

    # tiles = (tiles.build_url(scale_factor="@2x"),)
    provider = DARK_BASEMAPS[basemap].copy()
    # fig.add_tile(provider, retina=True)

    fig.add_tile(provider, retina=True)

    fig.toolbar.logo = None
    fig.background_fill_color = "#0b1120"
    fig.border_fill_color = "#0b1120"
    fig.outline_line_color = None
    fig.axis.visible = False
    fig.grid.visible = False

    if region is not None:
        add_region_outline(fig, region, to_mercator=True)
        try:
            n_cells = len(region.polygons)
        except Exception:
            n_cells = None

        if plot_cells:
            if n_cells is not None and n_cells <= 50_000:
                add_region_cells(fig, region, to_mercator=True)
    if region is not None:
        return fig, n_cells, region.dh, [xmin, xmax], [ymin, ymax]
    else:
        return fig, None, None, (None, None), (None, None)


def parse_time_window_strings(tw_strings):
    """Parse 'YYYY-MM-DD to YYYY-MM-DD' strings into time window dicts."""
    parsed = []

    for idx, s in enumerate(tw_strings or []):
        if " to " not in s:
            continue
        start_str, end_str = s.split(" to ", 1)
        try:
            start = datetime.fromisoformat(start_str.strip())
            end = datetime.fromisoformat(end_str.strip())
        except ValueError:
            continue

        length_days = (end - start).days
        parsed.append(
            {
                "label": f"Window {idx + 1}",
                "start": start,
                "end": end,
                "start_str": start_str.strip(),
                "end_str": end_str.strip(),
                "length_days": length_days,
            }
        )

    return parsed


def build_time_windows_figure(parsed_windows, height=180):
    """Build an interactive timeline of time windows."""
    if not parsed_windows:
        fig = figure(
            x_axis_type="datetime",
            height=height,
            sizing_mode="stretch_width",
            toolbar_location="above",
            tools="xwheel_zoom,xpan,box_zoom,reset",
            active_scroll="xwheel_zoom",
        )
        fig.title.text = "No time windows defined"
        fig.yaxis.visible = False
        fig.grid.visible = False
        fig.background_fill_color = "#020617"
        fig.border_fill_color = "#020617"
        fig.outline_line_color = None
        return fig

    windows_sorted = sorted(parsed_windows, key=lambda tw: tw["start"])
    lane_last_end = []
    lane_index = []

    for tw in windows_sorted:
        start = tw["start"]
        end = tw["end"]
        assigned = False
        for i, last_end in enumerate(lane_last_end):
            if start >= last_end:
                lane_last_end[i] = end
                lane_index.append(i)
                assigned = True
                break
        if not assigned:
            lane_last_end.append(end)
            lane_index.append(len(lane_last_end) - 1)

    n_lanes = len(lane_last_end)
    y = [li + 0.5 for li in lane_index]
    bar_height = 0.6

    starts = [tw["start"] for tw in windows_sorted]
    ends = [tw["end"] for tw in windows_sorted]

    top = [yy + bar_height / 2 for yy in y]
    bottom = [yy - bar_height / 2 for yy in y]

    source = ColumnDataSource(
        {
            "start": starts,
            "end": ends,
            "y": y,
            "top": top,
            "bottom": bottom,
            "label": [tw["label"] for tw in windows_sorted],
            "start_str": [tw["start_str"] for tw in windows_sorted],
            "end_str": [tw["end_str"] for tw in windows_sorted],
            "length_days": [tw["length_days"] for tw in windows_sorted],
        }
    )

    x_min = min(starts)
    x_max = max(ends)
    pad = (x_max - x_min) * 0.05 if x_max > x_min else None

    fig = figure(
        x_axis_type="datetime",
        height=height,
        sizing_mode="stretch_width",
        toolbar_location="above",
        tools="xwheel_zoom,xpan,reset",
        active_scroll="xwheel_zoom",
    )

    if pad is not None:
        fig.x_range = Range1d(x_min - pad, x_max + pad)

    fig.y_range = Range1d(-0.2, n_lanes + 0.8)

    fig.quad(
        left="start",
        right="end",
        top="top",
        bottom="bottom",
        source=source,
        fill_color="#38bdf8",
        fill_alpha=0.6,
        line_color="#0ea5e9",
        line_width=1.0,
    )

    hover = HoverTool(
        tooltips=[
            ("Window", "@label"),
            ("Start", "@start_str"),
            ("End", "@end_str"),
            ("Length (days)", "@length_days"),
        ],
        mode="mouse",
    )
    fig.add_tools(hover)

    today = datetime.today()
    if today <= x_max and (x_max - today) <= timedelta(days=5 * 365):
        today_span = Span(
            location=today,
            dimension="height",
            line_color="#f97316",
            line_width=2,
            line_dash="dashed",
        )
        fig.add_layout(today_span)

    fig.yaxis.visible = False
    fig.ygrid.visible = False
    fig.xgrid.visible = False
    fig.background_fill_color = "#0b1120"
    fig.border_fill_color = "#0b1120"
    fig.outline_line_color = None
    fig.xaxis.formatter = DatetimeTickFormatter(
        years="%Y",
        months="%b %Y",
        days="%d %b %Y",
        hours="%d %b %Y",
    )
    fig.xaxis.major_label_orientation = np.pi / 2
    fig.xaxis.major_label_text_font_size = "6pt"
    fig.axis.major_label_text_color = "#e5e7eb"
    fig.axis.major_tick_line_color = "#6b7280"
    fig.axis.minor_tick_line_color = None
    fig.axis.axis_line_color = "#6b7280"
    fig.title.text = ""

    fig.min_border_top = 10

    return fig
