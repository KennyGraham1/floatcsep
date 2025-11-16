import panel as pn

from ..manifest import Manifest


def build_forecasts_view(manifest: Manifest) -> pn.layout.Panel:
    content = pn.pane.Markdown(
        "## Forecasts\n\n"
        "Forecast maps and model/time-window selectors will be displayed here.",
        sizing_mode="stretch_width",
    )
    return pn.Column(content, sizing_mode="stretch_both")
