import panel as pn
from ..manifest import Manifest

from .utils import (
    build_region_basemap,
    parse_time_window_strings,
    build_time_windows_figure,
    fmt_coord,
    make_doi_badge,
)


def _experiment_overview_block(manifest: Manifest) -> pn.panel:
    """Title block at the top of the Experiment tab."""
    name = manifest.name or "Experiment"
    text = f"## {name}"
    return pn.pane.Markdown(text, sizing_mode="stretch_width")


def _metadata_section(manifest: Manifest) -> pn.Column:
    """High-level experiment metadata: authors, DOIs, journal, versions, etc."""
    lines = []

    # EXP CLASS
    exp_time = getattr(manifest, "exp_time", None)
    if exp_time:
        lines.append(f"**Experiment Class:** `{exp_time}`")

    # EXP CLASS
    model_type = getattr(manifest, "exp_class", None)
    if model_type:
        lines.append(f"**Model Type:** `{model_type}`")

    # Authors
    authors = getattr(manifest, "authors", None)
    if authors:
        if isinstance(authors, (list, tuple)):
            authors_str = ", ".join(str(a) for a in authors)
        else:
            authors_str = str(authors)
        lines.append(f"**Authors:** {authors_str}")

    # Experiment DOI (e.g. Zenodo for the experiment bundle)
    doi = getattr(manifest, "doi", None)
    if doi:
        badge = make_doi_badge(doi)
        lines.append(f"**DOI:** {badge}")

    # Manuscript / paper DOI
    manuscript_doi = getattr(manifest, "manuscript_doi", None)
    if manuscript_doi:
        lines.append(f"**Manuscript DOI:** `{manuscript_doi}`")

    # Journal name, if present
    journal = getattr(manifest, "journal", None)
    if journal:
        lines.append(f"**Journal:** {journal}")

    # Last run timestamp
    last_run = getattr(manifest, "last_run", None)
    if last_run:
        lines.append(f"**Last run:** {last_run}")

    # floatCSEP version: prefer manifest override, else package
    fc_ver = getattr(manifest, "floatcsep_version", None)
    if fc_ver:
        lines.append(f"**floatCSEP version:** `{fc_ver}`")

    # pyCSEP version: prefer manifest override, else package
    pycsep_ver = getattr(manifest, "pycsep_version", None)
    if pycsep_ver:
        lines.append(f"**pyCSEP version:** `{pycsep_ver}`")

    license_ = getattr(manifest, "license", None)
    if license:
        lines.append(f"**LICENSE:** `{license_}`")

    if len(lines) == 1:
        lines.append("_No experiment metadata available._")

    section = pn.pane.Markdown(
        "\n\n".join(lines),
        sizing_mode="stretch_width",
        styles={
            "font-size": "11px",
            "line-height": "1",
        },
    )
    return pn.Column(section, margin=(4, 0, 4, 4))


def _temporal_section(manifest: Manifest) -> pn.Column:
    """Markdown summary for the temporal configuration."""
    start_date = manifest.start_date
    end_date = manifest.end_date
    n_intervals = getattr(manifest, "n_intervals", None)
    exp_class = getattr(manifest, "exp_class", None)
    horizon = getattr(manifest, "horizon", None)
    offset = getattr(manifest, "offset", None)
    growth = getattr(manifest, "growth", None)
    time_windows = getattr(manifest, "time_windows", None) or []

    lines = []

    if exp_class:
        exp_str = (
            "Time-Independent"
            if exp_class in ("ti", "time-independent", "Time-Independent")
            else "Time-Dependent"
        )
        lines.append(f"**Class:** {exp_str}")
    lines.append(f"**Start Date:** {start_date}")
    lines.append(f"**End Date:** {end_date}")

    if horizon:
        lines.append(f"**Forecast Horizon:** {horizon}")
    if offset:
        lines.append(f"**Window Offset:** {offset}")
    if growth:
        lines.append(f"**Window Growth:** {growth}")

    tw_str = f"**Time Windows:** {n_intervals}\n"
    for tw in time_windows:
        tw_str += f" - {tw}\n\n"
    lines.append(tw_str)

    section = pn.pane.Markdown(
        "\n\n".join(lines),
        sizing_mode="stretch_width",
        styles={"font-size": "11px", "line-height": "0.6"},
    )
    return pn.Column(section, margin=(0, 0, 0, 8))


def _spatial_section(manifest: Manifest) -> pn.Column:

    region = getattr(manifest, "region", None)
    region_name = getattr(region, "name", None) if region is not None else None

    mag_min = getattr(manifest, "mag_min", None)
    mag_max = getattr(manifest, "mag_max", None)
    mag_bin = getattr(manifest, "mag_bin", None)
    depth_min = getattr(manifest, "depth_min", None)
    depth_max = getattr(manifest, "depth_max", None)

    lines = []

    if region_name:
        lines.append(f"**Region:** {region_name}")
    elif isinstance(region, str):
        lines.append(f"**Region:** {region}")
    else:
        lines.append("**Region:** \n")

    lines.append(f"**Magnitude range:** [{mag_min}, {mag_max}]")
    lines.append(f"**Magnitude bin:**  ΔM = {mag_bin}")

    if depth_min is not None and depth_max is not None:
        lines.append(f"**Depth range:** [{depth_min}, {depth_max}] km")

    section = pn.pane.Markdown(
        "\n\n".join(lines),
        sizing_mode="stretch_width",
        styles={
            "font-size": "11px",
            "line-height": "0.6",
        },
    )
    return pn.Column(section, margin=(0, 0, 0, 8))


def _models_section(manifest: Manifest) -> pn.Column:
    models = manifest.models or []

    lines = []
    for model in models:
        lines.append(f"### {model['name']}")
        if model.get("forecast_unit", False):
            lines.append(f" - **Forecast Unit:** {model['forecast_unit']} years")
        if model.get("path", False):
            lines.append(f" - **Path:** `{model['path']}`")
        if model.get("giturl", False):
            lines.append(f" - **Git URL:** `{model['giturl']}`")
        if model.get("git_hash", False):
            lines.append(f" - **Git Hash:** `{model['git_hash']}`")
        if model.get("zenodo_id", False):
            lines.append(f" - **Zenodo ID:** {model['zenodo_id']}")
        if model.get("authors", False):
            lines.append(f" - **Authors:** {model['authors']}")
        if model.get("doi"):
            badge = make_doi_badge(model["doi"])
            lines.append(f"- **DOI:** {badge}")
        if model.get("func", False):
            lines.append(f" - **Call Function:** {model['func']}")
        if model.get("func_kwargs", False):
            lines.append(f" - **Function Arguments:** {model['func_kwargs']}")
        if model.get("fmt", False):
            lines.append(f" - **Forecast Format:** {model['fmt']}")

    section = pn.pane.Markdown(
        "\n".join(lines),
        sizing_mode="stretch_width",
        styles={
            "font-size": "11px",
            "line-height": "1",
        },
    )

    return pn.Column(section, margin=(0, 0, 0, 8))


def _tests_section(manifest: Manifest) -> pn.Column:
    tests = manifest.tests or []

    lines = []
    for test in tests:
        lines.append(f"### {test['name']}")
        if test.get("func", False):
            lines.append(f" - **Function:** {test['func']}")
        if test.get("func_kwargs", False):
            lines.append(f" - **Function Arguments:** {test['func_kwargs']}")
        if test.get("ref_model", False):
            lines.append(f" - **Reference Model:** {test['ref_model']}")

    section = pn.pane.Markdown(
        "\n\n".join(lines),
        sizing_mode="stretch_width",
        styles={
            "font-size": "11px",
            "line-height": "0.6",
        },
    )

    return pn.Column(section, margin=(0, 0, 0, 8))


def _run_config_section(manifest: Manifest) -> pn.pane.Markdown:
    run_mode = getattr(manifest, "run_mode", None)
    run_dir = getattr(manifest, "run_dir", None)
    config_file = getattr(manifest, "config_file", None)
    model_config = getattr(manifest, "model_config", None)
    test_config = getattr(manifest, "test_config", None)

    lines = ["#### Run & configuration"]

    if run_mode:
        lines.append(f"- **Run mode:** {run_mode.capitalize()}")
    if run_dir:
        lines.append(f"- **Results directory:** `{run_dir}`")
    if config_file:
        lines.append(f"- **Experiment config:** `{config_file}`")
    if model_config:
        lines.append(f"- **Models config:** `{model_config}`")
    if test_config:
        lines.append(f"- **Tests config:** `{test_config}`")

    lines.append(f"- **Host:** `local`")

    if len(lines) == 1:
        lines.append("_No run/config information available._")

    return pn.pane.Markdown("\n".join(lines), sizing_mode="stretch_width")


def _build_region_panel(manifest: Manifest) -> pn.Column:
    """Region tab: basemap with experiment region overlay + compact metadata."""
    region = getattr(manifest, "region", None)
    fig, n_cells, dh, (lon_min, lon_max), (lat_min, lat_max) = build_region_basemap(region)
    fig_pane = pn.pane.Bokeh(fig, sizing_mode="stretch_width")

    line1_parts = []
    if n_cells is not None:
        line1_parts.append(f"**Cells:** {n_cells}")
    if dh is not None:
        line1_parts.append(f"**Δh:** {dh}")

    line2_parts = []
    if lon_min is not None and lon_max is not None:
        line2_parts.append(f"**Longitude range:** [{fmt_coord(lon_min)}, {fmt_coord(lon_max)}]")
    if lat_min is not None and lat_max is not None:
        line2_parts.append(f"**Latitude range:** [{fmt_coord(lat_min)}, {fmt_coord(lat_max)}]")

    if not line1_parts and not line2_parts:
        meta_text = "_No region metadata available._"
    else:
        meta_lines = []
        meta_lines.append("  ".join(line1_parts) if line1_parts else "")
        meta_lines.append("  ".join(line2_parts) if line2_parts else "")
        meta_text = "\n\n".join(l for l in meta_lines if l)

    meta_pane = pn.pane.Markdown(
        meta_text,
        sizing_mode="stretch_width",
        styles={
            "font-size": "09px",
            "line-height": "0.8",
        },
    )

    return pn.Column(
        fig_pane,
        meta_pane,
        sizing_mode="stretch_both",
    )


def _build_time_windows_panel(manifest: Manifest) -> pn.Column:
    """Time windows tab: interactive timeline of forecast intervals."""
    tw_strings = getattr(manifest, "time_windows", None) or []
    parsed = parse_time_window_strings(tw_strings)
    n_intervals = getattr(manifest, "n_intervals", None)

    header_lines = []
    if n_intervals is not None:
        header_lines.append(f"Number of windows: **{n_intervals}**")

    header_md = pn.pane.Markdown(
        "\n\n".join(header_lines),
        sizing_mode="stretch_width",
        styles={"font-size": "11px"},
    )

    fig = build_time_windows_figure(parsed, height=180)
    fig_pane = pn.pane.Bokeh(fig, sizing_mode="stretch_width")

    return pn.Column(
        header_md,
        pn.Spacer(height=4),
        fig_pane,
        sizing_mode="stretch_width",
    )


def _build_right_tabs(manifest: Manifest) -> pn.Tabs:
    """Right-hand panel: Region | Time Windows tabs."""
    region_panel = _build_region_panel(manifest)
    time_panel = _build_time_windows_panel(manifest)

    return pn.Tabs(
        ("Region", region_panel),
        ("Time Windows", time_panel),
        sizing_mode="stretch_width",
    )


def build_experiment_view(manifest: Manifest) -> pn.layout.Panel:
    """Build the Experiment tab view.

    Left: metadata (overview + accordion sections).
    Right: region map and time-window timeline.
    """
    overview = _experiment_overview_block(manifest)

    meta_panel = pn.Column(_metadata_section(manifest), margin=(4, 0, 4, 4))
    temporal_panel = pn.Column(_temporal_section(manifest), margin=(4, 0, 4, 4))
    spatial_panel = pn.Column(_spatial_section(manifest), margin=(4, 0, 4, 4))
    models_panel = pn.Column(_models_section(manifest), margin=(4, 0, 4, 4))
    tests_panel = pn.Column(_tests_section(manifest), margin=(4, 0, 4, 4))
    run_cfg = _run_config_section(manifest)

    sections = pn.Accordion(
        ("Metadata", meta_panel),
        ("Temporal Configuration", temporal_panel),
        ("Region Definition", spatial_panel),
        ("Models", models_panel),
        ("Evaluations", tests_panel),
        ("Run Configuration", run_cfg),
        sizing_mode="stretch_width",
        active_header_background="#0b1120",
        header_background="#0b1120",
        header_color="#e5e7eb",
        styles={"stroke": "#e5e7eb"},
    )

    left = pn.Column(
        overview,
        pn.layout.Divider(),
        sections,
        width=380,
    )

    right = _build_right_tabs(manifest)

    return pn.Row(
        left,
        pn.Spacer(width=25),
        right,
        sizing_mode="stretch_both",
    )
