"""
Minimal Panel app module for floatCSEP results (static-friendly).

Goals (per user spec):
- Three tabs: Experiment | Forecasts | Results.
- Always include all time windows.
- Use existing figure files resolved via experiment.registry.get_figure_key(...).
- No downloads yet. No hosting logic yet. Keep it small.
- Prefer keeping figures in-place; app references them by *relative paths*.

Usage (build once, then open index.html):

    from panel_app import save_app
    save_app(experiment, output_html=experiment.registry.abs(
        experiment.registry.run_dir / "index.html"))

If you want to preview before saving:

    from panel_app import make_app, build_manifest
    manifest = build_manifest(experiment)
    app = make_app(manifest)
    app.servable()  # panel serve your_script.py

Notes:
- This module expects a floatCSEP Experiment-like object with:
  - .name, .start_date, .end_date, .magnitudes, .region (optional)
  - .models (each with .name)
  - .tests (each with .name and .markdown; .plot_args optional)
  - .time_windows (iterable)
  - .registry.get_figure_key(...) and .registry.run_dir, .registry.abs(path)
- It collects figure paths and converts them to *relative* paths from a chosen app root
  (default: the experiment.registry.run_dir where index.html will live).
- The app uses CDN resources by default (small HTML). For offline, set resources="inline".
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Tuple

import panel as pn
from floatcsep.utils.helpers import timewindow2str

# ---- Small helpers ---------------------------------------------------------


def _rel(path: os.PathLike | str, base: os.PathLike | str) -> str:
    """POSIX-style relative path for HTML usage."""
    rel = os.path.relpath(str(path), str(base))
    return rel.replace("\\", "/")


@dataclass
class Manifest:
    name: str
    date_range: str
    magnitudes: List[float]
    region: Optional[str]
    models: List[str]
    tests: List[str]
    time_windows: List[str]
    # Figures
    catalog: Dict[str, str]  # keys: {"map": path, "time": path}
    # forecasts[(tw, model)] = path
    forecasts: Dict[Tuple[str, str], str]
    # results_main[(tw, test)] = path
    results_main: Dict[Tuple[str, str], str]
    # results_model[(tw, test, model)] = path (optional entries)
    results_model: Dict[Tuple[str, str, str], str]
    # Absolute base dir where index.html will be placed (for reference only)
    app_root: str


# ---- Manifest builder ------------------------------------------------------


def build_manifest(experiment: Any, app_root: Optional[str] = None) -> Manifest:
    """Collect minimal info + figure paths into a manifest.

    Paths are made relative to app_root. If not provided, app_root defaults to
    experiment.registry.run_dir (index.html typically lives there).
    """
    reg = experiment.registry
    if app_root is None:
        app_root = reg.abs(reg.run_dir)

    # Summary fields
    name = getattr(experiment, "name", "Experiment")
    start = getattr(experiment, "start_date", "?")
    end = getattr(experiment, "end_date", "?")
    date_range = f"{start} — {end}"
    magnitudes = list(getattr(experiment, "magnitudes", []))
    region = getattr(experiment, "region", None)

    # Time windows (string form)
    tw_all = []
    for tw in getattr(experiment, "time_windows", []):
        tw_all.append(timewindow2str(tw))

    # Models/tests
    models = [getattr(m, "name", str(m)) for m in getattr(experiment, "models", [])]
    tests = [getattr(t, "name", str(t)) for t in getattr(experiment, "tests", [])]

    # Catalog figures
    cat = {}
    try:
        cat_map = reg.get_figure_key("main_catalog_map") + ".png"
        cat_time = reg.get_figure_key("main_catalog_time") + ".png"
        cat["map"] = _rel(cat_map, app_root)
        cat["time"] = _rel(cat_time, app_root)
    except Exception:
        # Leave missing keys out; UI will handle gracefully
        pass

    # Forecast figures (tw, model)
    fcasts: Dict[Tuple[str, str], str] = {}
    for tw_str in tw_all:
        for model_name in models:
            try:
                p = reg.get_figure_key(tw_str, "forecasts", model_name)
                fcasts[(tw_str, model_name)] = _rel(p, app_root)
            except Exception:
                # Some (tw, model) may not exist; skip
                continue

    # Results figures
    res_main: Dict[Tuple[str, str], str] = {}
    res_model: Dict[Tuple[str, str, str], str] = {}
    for tw_str in tw_all:
        for test_name in tests:
            # Main test fig
            try:
                p = reg.get_figure_key(tw_str, test_name)
                res_main[(tw_str, test_name)] = _rel(p, app_root)
            except Exception:
                pass
            # Per-model figs (optional)
            for model_name in models:
                try:
                    p = reg.get_figure_key(tw_str, f"{test_name}_{model_name}")
                    res_model[(tw_str, test_name, model_name)] = _rel(p, app_root)
                except Exception:
                    continue

    return Manifest(
        name=name,
        date_range=date_range,
        magnitudes=magnitudes,
        region=region,
        models=models,
        tests=tests,
        time_windows=tw_all,
        catalog=cat,
        forecasts=fcasts,
        results_main=res_main,
        results_model=res_model,
        app_root=str(app_root),
    )


# ---- UI construction -------------------------------------------------------


def _safe_image(path: Optional[str]) -> pn.pane.PaneBase:
    if path and os.path.exists(path):
        # When saving standalone, keeping embed=False makes HTML smaller
        return pn.pane.Image(path, sizing_mode="stretch_width", max_height=600, embed=False)
    # If relative path from manifest, allow missing file at Python runtime; browser will try to fetch
    if path:
        return pn.pane.Image(path, sizing_mode="stretch_width", max_height=600, embed=False)
    return pn.pane.Markdown("*No figure available.*")


def make_app(manifest: Manifest) -> pn.Tabs:
    pn.extension()

    # --- Tab 1: Experiment --------------------------------------------------
    header_md = [
        f"# {manifest.name}",
        f"**Date range:** {manifest.date_range}",
        f"**Magnitudes:** {', '.join(map(str, manifest.magnitudes)) if manifest.magnitudes else '—'}",
        f"**Region:** {manifest.region if manifest.region else '—'}",
        f"**Models:** {', '.join(manifest.models) if manifest.models else '—'}",
        f"**Tests:** {', '.join(manifest.tests) if manifest.tests else '—'}",
    ]
    exp_summary = pn.pane.Markdown("\n\n".join(header_md), sizing_mode="stretch_width")

    # Time windows table (always include all)
    tw_table = pn.pane.Markdown(
        (
            "\n".join(["### Time windows", *[f"- {tw}" for tw in manifest.time_windows]])
            if manifest.time_windows
            else "*No time windows available.*"
        ),
        sizing_mode="stretch_width",
    )

    # Catalog figures
    cat_row = pn.Row(
        _safe_image(manifest.catalog.get("map")),
        _safe_image(manifest.catalog.get("time")),
        sizing_mode="stretch_width",
    )
    tab_experiment = pn.Column(
        exp_summary, tw_table, pn.Spacer(height=10), cat_row, sizing_mode="stretch_both"
    )

    # --- Tab 2: Forecasts ---------------------------------------------------
    model_opts = manifest.models or ["—"]
    tw_opts = manifest.time_windows or ["—"]
    sel_model = pn.widgets.Select(name="Model", options=model_opts, value=model_opts[0])
    sel_tw = pn.widgets.Select(name="Time window", options=tw_opts, value=tw_opts[0])

    def _current_forecast_path() -> Optional[str]:
        key = (sel_tw.value, sel_model.value)
        return manifest.forecasts.get(key)

    def _forecast_image(model: str, tw: str):
        return _safe_image(manifest.forecasts.get((tw, model)) + ".png")

    forecast_img = pn.bind(_forecast_image, sel_model, sel_tw)

    tab_forecasts = pn.Column(
        pn.Row(sel_model, sel_tw, sizing_mode="stretch_width"),
        pn.layout.HSpacer(height=5),
        forecast_img,
        sizing_mode="stretch_both",
    )

    # --- Tab 3: Results -----------------------------------------------------
    test_opts = manifest.tests or ["—"]
    sel_test = pn.widgets.Select(name="Test", options=test_opts, value=test_opts[0])
    sel_tw_res = pn.widgets.Select(name="Time window", options=tw_opts, value=tw_opts[0])

    def _main_result_image(test: str, tw: str):
        return _safe_image(manifest.results_main.get((tw, test)) + ".png")

    main_result_img = pn.bind(_main_result_image, sel_test, sel_tw_res)

    # Optional: per-model grid (only show entries that exist for the selection)
    def _per_model_grid(test: str, tw: str) -> pn.layout.Panel: ...

    per_model_view = pn.bind(_per_model_grid, sel_test, sel_tw_res)

    # Optional description: use test.markdown text — here we don’t have live objects,
    # but you can inject it into the manifest later. For now, show a placeholder title.
    # If you choose to add test descriptions: extend Manifest with test_markdown: Dict[str, str].
    test_desc = pn.pane.Markdown(
        "*(Test description goes here — provide `test.markdown` in the manifest to display it.)*",
        sizing_mode="stretch_width",
    )

    tab_results = pn.Column(
        pn.Row(sel_test, sel_tw_res, sizing_mode="stretch_width"),
        pn.layout.HSpacer(height=5),
        main_result_img,
        pn.layout.Divider(),
        pn.pane.Markdown("### Per-model results"),
        per_model_view,
        pn.layout.Divider(),
        test_desc,
        sizing_mode="stretch_both",
    )

    tabs = pn.Tabs(
        ("Experiment", tab_experiment),
        ("Forecasts", tab_forecasts),
        ("Results", tab_results),
        sizing_mode="stretch_both",
    )
    return tabs


# ---- Save helper -----------------------------------------------------------


def save_app(
    experiment: Any, output_html: str, resources: str = "cdn", app_root: Optional[str] = None
) -> Manifest:
    """Build manifest, assemble app, and save a standalone HTML.

    Parameters
    ----------
    experiment : Any
        floatCSEP Experiment-like object.
    output_html : str
        Target HTML path (e.g., experiment.registry.abs(run_dir / "index.html")).
    resources : {"cdn", "inline"}
        Panel resource strategy. Use "inline" for fully self-contained HTML
        (bigger file); use "cdn" for smaller file (internet access required).
    app_root : Optional[str]
        Base folder used to compute *relative* figure paths. Defaults to
        experiment.registry.run_dir.

    Returns
    -------
    Manifest
        The manifest used to build the app (useful for testing or logging).
    """
    manifest = build_manifest(experiment, app_root=app_root)
    print(manifest)
    app = make_app(manifest)

    # Ensure output dir exists
    os.makedirs(os.path.dirname(output_html), exist_ok=True)

    # Save a standalone (no Python server) HTML.
    # embed=True captures widget state for client-side interaction.
    import panel.io.save as _iosave  # module

    _iosave.save(app, str(output_html), title=manifest.name, resources=resources, embed=True)

    return manifest
