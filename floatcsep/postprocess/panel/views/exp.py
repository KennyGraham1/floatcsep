import panel as pn
from ..manifest import Manifest


def _experiment_overview_block(manifest: Manifest) -> pn.panel:
    name = manifest.name or "Experiment"

    text = f"## {name}"

    return pn.pane.Markdown(text, sizing_mode="stretch_width")


def _temporal_section(manifest: Manifest) -> pn.Column:
    start_date = manifest.start_date
    end_date = manifest.end_date
    n_intervals = getattr(manifest, "n_intervals", None)
    exp_class = getattr(manifest, "exp_class", None)
    horizon = getattr(manifest, "horizon", None)
    offset = getattr(manifest, "offset", None)
    growth = getattr(manifest, "growth", None)
    time_windows = getattr(manifest, "time_windows", None)

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
        lines.append(f"*Forcast Horizon:* {horizon}")
    if offset:
        lines.append(f"**Window Offset:** {offset}")
    if growth:
        lines.append(f"**Window Growth:** {growth}")

    tw_str = f"**Time Windows:** {n_intervals}\n"
    for i in time_windows:
        tw_str += f" - {i}"
    lines.append(tw_str)

    section = pn.pane.Markdown(
        "\n\n".join(lines),
        sizing_mode="stretch_width",
        styles={
            "font-size": "11px",
            "line-height": "0.6",
        },
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
        lines.append(f"### {model["name"]}")
        if model.get("forecast_unit", False):
            lines.append(f" - **Forecast Unit:** {model["forecast_unit"]} years")
        if model.get("path", False):
            lines.append(f" - **Path:** {model["path"]}")
        if model.get("giturl", False):
            lines.append(f" - **Git URL:** {model["giturl"]}")
        if model.get("git_hash", False):
            lines.append(f" - **Git Hash:** {model["git_hash"]}")
        if model.get("zenodo_id", False):
            lines.append(f" - **Zenodo ID:** {model["zenodo_id"]}")
        if model.get("authors", False):
            lines.append(f" - **Authors:** {model["authors"]}")
        if model.get("doi", False):
            lines.append(f" - **DOI:** {model["doi"]}")
        if model.get("func", False):
            lines.append(f" - **Call Function:** {model["func"]}")
        if model.get("func_kwargs", False):
            lines.append(f" - **Function Arguments:** {model["func_kwargs"]}")
        if model.get("fmt", False):
            lines.append(f" - **Forecast Format:** {model["fmt"]}")

    section = pn.pane.Markdown(
        "\n\n".join(lines),
        sizing_mode="stretch_width",
        styles={
            "font-size": "11px",
            "line-height": "0.6",
        },
    )

    return pn.Column(section, margin=(0, 0, 0, 8))


def _tests_section(manifest: Manifest) -> pn.Column:
    tests = manifest.tests or []

    lines = []
    for test in tests:
        lines.append(f"### {test["name"]}")
        if test.get("func", False):
            lines.append(f" - **Function:** {test["func"]}")
        if test.get("func_kwargs", False):
            lines.append(f" - **Function Arguments:** {test["func_kwargs"]}")
        if test.get("ref_model", False):
            lines.append(f" - **Reference Model:** {test["ref_model"]}")

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

    if len(lines) == 1:
        lines.append("_No run/config information available._")

    return pn.pane.Markdown("\n".join(lines), sizing_mode="stretch_width")


def build_experiment_view(manifest: Manifest) -> pn.layout.Panel:
    """Build the Experiment tab view.

    Left: metadata (overview + collapsible sections).
    Right: placeholder panel for future context-dependent content.
    """
    # --- LEFT PANEL: overview + grouped, collapsible sections ---
    overview = _experiment_overview_block(manifest)

    temporal = _temporal_section(manifest)
    temporal_panel = pn.Column(temporal, margin=(4, 0, 4, 4))

    spatial = _spatial_section(manifest)
    spatial_panel = pn.Column(spatial, margin=(4, 0, 4, 4))

    models = _models_section(manifest)
    models_panel = pn.Column(models, margin=(4, 0, 4, 4))

    tests = _tests_section(manifest)
    tests_panel = pn.Column(tests, margin=(4, 0, 4, 4))

    run_cfg = _run_config_section(manifest)

    sections = pn.Accordion(
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
    # sections.active = [0]  # open temporal by default

    left = pn.Column(
        overview,
        pn.layout.Divider(),
        sections,
        # sizing_mode="stretch_both",
        width=380,
    )

    # --- RIGHT PANEL: placeholder for now ---
    right_placeholder = pn.pane.Markdown(
        "### Experiment details\n\n"
        "This area will display detailed views, figures, or controls\n"
        "depending on what you select in the left panel.\n\n"
        "- For example: time-window plots when you expand *Temporal configuration*.\n"
        "- Or region map preview when you expand *Spatial & magnitude*.\n",
        sizing_mode="stretch_both",
    )

    right = pn.Column(
        right_placeholder,
        # sizing_mode="stretch_both",
    )

    # Row: left metadata panel + right detail panel
    return pn.Row(
        left,
        right,
        sizing_mode="stretch_both",
    )
