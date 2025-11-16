import panel as pn

from ..manifest import Manifest


def build_results_view(manifest: Manifest) -> pn.layout.Panel:
    content = pn.pane.Markdown(
        "## Test results\n\n"
        "Statistical test results and per-model views will be displayed here.",
        sizing_mode="stretch_width",
    )
    return pn.Column(content, sizing_mode="stretch_both")
