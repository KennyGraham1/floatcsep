import panel as pn

from ..manifest import Manifest


def build_catalogs_view(manifest: Manifest) -> pn.layout.Panel:
    content = pn.pane.Markdown(
        "## Catalogs\n\n" "Catalog maps and time series will be displayed here.",
        sizing_mode="stretch_width",
    )
    return pn.Column(content, sizing_mode="stretch_both")
