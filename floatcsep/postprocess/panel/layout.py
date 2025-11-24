import panel as pn
from panel.template import MaterialTemplate
from panel.theme.material import MaterialDarkTheme
from panel.widgets import MenuButton
from panel.layout import VSpacer, HSpacer
from panel import indicators

from .manifest import Manifest
from .views.exp import build_experiment_view
from .views.cats import build_catalogs_view
from .views.forecasts import build_forecasts_view
from .views.results import build_results_view


from floatcsep import __version__ as FLOATCSEP_VERSION

FLOATCSEP_REPO_URL = "https://github.com/cseptesting/floatcsep"

DASHBOARD_CSS = """
@font-face {
  font-family: "NotoSans";
  src: url("/artifacts/NotoSans-Regular.ttf") format("truetype");
  font-weight: 400;
  font-style: normal;
  font-display: swap;
}
@font-face {
  font-family: "NotoSans";
  src: url("/artifacts/NotoSans-Bold.ttf") format("truetype");
  font-weight: 700;
  font-style: normal;
  font-display: swap;
}

:root {
  --design-background-color: #020617;        /* page background */
  --design-background-text-color: #e5e7eb;

  --design-surface-color: #020617;           /* background of cards / surfaces / buttons */ 
  --design-surface-text-color: #e5e7eb;      /* text of cards / surfaces / buttons */    

  --design-primary-color: #14b8a6;
  --design-primary-text-color: #020617;

  --design-secondary-color: #f59e0b;
  --design-secondary-text-color: #e5e7eb;
}

/* Base font */
body {
  font-family: "NotoSans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

/* Override Material / Bokeh default fonts */
.bk, .bk * {
  font-family: "NotoSans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}
.mdc-typography, .mdc-typography * {
  font-family: "NotoSans", system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

/* Headings */
h1, h2, h3 {
  font-family: "NotoSans", system-ui, sans-serif !important;
  font-weight: 700;
}


"""


def _build_tabs(manifest: Manifest) -> pn.Tabs:
    tab_experiment = build_experiment_view(manifest)
    tab_catalogs = build_catalogs_view(manifest)
    tab_forecasts = build_forecasts_view(manifest)
    tab_results = build_results_view(manifest)

    tabs = pn.Tabs(
        ("Experiment", tab_experiment),
        ("Catalogs", tab_catalogs),
        ("Forecasts", tab_forecasts),
        ("Results", tab_results),
        tabs_location="left",
        dynamic=True,
        sizing_mode="fixed",
    )
    return tabs


def _build_header_menu() -> MenuButton:

    return MenuButton(
        name="☰",
        button_type="default",
        width=32,
        height=32,
        margin=(25, 25, 25, 25),
        items=[
            ("Citation", "citation"),
            ("Imprint", "imprint"),
            ("Data Protection", "privacy"),
        ],
    )


def _build_custom_header(manifest: Manifest) -> pn.Row:
    logo = pn.pane.PNG(
        "/artifacts/logo.png",
        height=56,
        align="center",
        margin=(0, 12, 0, 0),
        link_url=FLOATCSEP_REPO_URL,
    )

    title = pn.pane.Markdown(
        f"Experiment Dashboard",
        sizing_mode="stretch_width",
        margin=(0, 0, 0, 0),
        styles={
            "font-size": "24px",
            "font-weight": "400",
        },
    )

    header_row = pn.Row(
        logo,
        title,
        HSpacer(),
        _build_header_menu(),
        sizing_mode="stretch_width",
        align="center",
        margin=(15, 0, 0, -20),
    )
    return header_row


def _status_chip(manifest: Manifest) -> pn.pane.Markdown:
    # TODO: later, inspect experiment results
    label = "Status: 🟢 OK"
    return pn.pane.Markdown(
        label,
        margin=(0, 12, 0, 0),
        styles={
            "font-size": "9px",
            "opacity": "0.75",
        },
    )


def _build_meta_bar(manifest: Manifest, busy_spinner: pn.viewable.Viewable) -> pn.Row:
    items = []

    def _chip(text: str) -> pn.pane.Markdown:
        return pn.pane.Markdown(
            text,
            margin=(0, 12, 0, 0),
            styles={"font-size": "9px", "opacity": "0.6"},
        )

    if getattr(manifest, "name", None):
        items.append(_chip(f"**Name**: {manifest.name}"))

    if getattr(manifest, "date_range", None):
        items.append(_chip(f"**Time frame**: {manifest.date_range}"))

    if getattr(manifest, "magnitudes", None):
        m_min = min(manifest.magnitudes)
        m_max = max(manifest.magnitudes)
        items.append(_chip(f"**Magnitude range**: {m_min} — {m_max}"))

    if getattr(manifest, "models", None):
        items.append(_chip(f"**Models**: {len(manifest.models)}"))

    if getattr(manifest, "tests", None):
        items.append(_chip(f"**Tests**: {len(manifest.tests)}"))

    items.append(_status_chip(manifest))

    if getattr(manifest, "doi", None):
        doi = manifest.doi.strip()
        doi_badge_html = (
            '<div style="display:flex;align-items:center;height:100%;">'
            f'<a href="https://doi.org/{doi}">'
            f'<img src="https://zenodo.org/badge/DOI/{doi}.svg" '
            f'alt="DOI" style="height:16px; vertical-align:middle;">'
            f"</a>"
        )
        items.append(
            pn.pane.HTML(doi_badge_html, margin=(6, 0, 0, 0), styles={"opacity": "0.85"})
        )

    if not items:
        return pn.Row()

    bar = pn.Row(
        *items,
        HSpacer(),
        busy_spinner,
        sizing_mode="stretch_width",
        align="center",
        margin=(-10, 10, -10, 0),
    )
    return bar


def _build_footer(manifest: Manifest) -> pn.Row:

    version = pn.pane.Markdown(
        f"**floatCSEP** v{FLOATCSEP_VERSION}",
        styles={"font-size": "9px", "opacity": "0.7"},
        margin=(2, 0, 0, 0),
    )

    github_logo = pn.pane.PNG(
        object="/artifacts/github_logo.png",
        height=18,
        margin=(0, 4, 0, 0),
        link_url=FLOATCSEP_REPO_URL,
    )

    rtd_logo = pn.pane.PNG(
        object="/artifacts/readthedocs_logo.png",
        height=18,
        margin=(0, 4, 0, 0),
        link_url="https://floatcsep.readthedocs.io/en/latest/",
    )

    csep_logo = pn.pane.PNG(
        object="/artifacts/csep_logo.png",
        height=18,
        margin=(0, 0, 0, 0),
        link_url="https://cseptesting.org/",
    )

    gi_logo = pn.pane.PNG(
        object="/artifacts/geoinquire_logo.png",
        height=18,
        margin=(0, 0, 0, 0),
        link_url="https://www.geo-inquire.eu/",
    )

    footer = pn.Row(
        version,
        HSpacer(),
        gi_logo,
        github_logo,
        rtd_logo,
        csep_logo,
        sizing_mode="stretch_width",
        margin=(4, 8, 4, 8),
    )
    return footer


def make_template_app(manifest: Manifest) -> MaterialTemplate:
    tabs = _build_tabs(manifest)

    template = MaterialTemplate(
        title="",
        site="",
        theme=MaterialDarkTheme,
        header_background="#020617",
        header_color="#e5e7eb",
        sidebar_width=0,
    )
    template.busy_indicator.visible = False

    busy_spinner = indicators.LoadingSpinner(
        value=False,
        size=14,
        height=18,
        width=18,
        margin=(8, 0, 0, 0),
    )

    def _sync_busy(event):
        busy_spinner.value = event.new

    pn.state.param.watch(_sync_busy, "busy")

    meta_bar = _build_meta_bar(manifest, busy_spinner)
    template.header[:] = [_build_custom_header(manifest)]

    footer = _build_footer(manifest)

    tabs_surface = pn.Column(
        tabs,
        sizing_mode="fixed",
        styles={
            "background-color": "#0b1120",
            "border-radius": "10px",
            "padding": "8px 8px 8px 0",
            "box-shadow": "0 10px 30px rgba(0, 0, 0, 0.4)",
            "min-height": "400px",
            "width": "100%",  # force full width inside MaterialTemplate
        },
        margin=(10, 0, 0, 0),
    )

    template.main[:] = [
        pn.Column(
            pn.layout.Divider(),
            meta_bar,
            tabs_surface,
            VSpacer(),
            footer,
            sizing_mode="stretch_width",
        )
    ]
    template.config.raw_css.append(DASHBOARD_CSS)
    return template
