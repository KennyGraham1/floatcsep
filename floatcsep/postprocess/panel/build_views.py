import panel as pn

from .manifest import Manifest


def build_experiment_view(manifest: Manifest) -> pn.layout.Panel:
    summary = pn.pane.Markdown(
        f"# {manifest.name}\n\n"
        f"**Date range:** {manifest.date_range}\n\n"
        f"**Models:** {', '.join(manifest.models) if manifest.models else '—'}\n\n"
        f"**Tests:** {', '.join(manifest.tests) if manifest.tests else '—'}",
        sizing_mode="stretch_width",
    )

    if manifest.time_windows:
        tw_lines = ["### Time windows"] + [f"- {tw}" for tw in manifest.time_windows]
        tw_block = pn.pane.Markdown("\n".join(tw_lines), sizing_mode="stretch_width")
    else:
        tw_block = pn.pane.Markdown("*No time windows available.*", sizing_mode="stretch_width")

    return pn.Column(summary, pn.Spacer(height=10), tw_block, sizing_mode="stretch_both")


def build_catalogs_view(manifest: Manifest) -> pn.layout.Panel:
    content = pn.pane.Markdown(
        "## Catalogs\n\n" "Catalog maps and time series will be displayed here.",
        sizing_mode="stretch_width",
    )
    return pn.Column(content, sizing_mode="stretch_both")


def build_forecasts_view(manifest: Manifest) -> pn.layout.Panel:
    content = pn.pane.Markdown(
        "## Forecasts\n\n"
        "Forecast maps and model/time-window selectors will be displayed here.",
        sizing_mode="stretch_width",
    )
    return pn.Column(content, sizing_mode="stretch_both")


def build_results_view(manifest: Manifest) -> pn.layout.Panel:
    content = pn.pane.Markdown(
        "## Test results\n\n"
        "Statistical test results and per-model views will be displayed here.",
        sizing_mode="stretch_width",
    )
    return pn.Column(content, sizing_mode="stretch_both")
