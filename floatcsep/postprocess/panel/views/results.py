from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

import panel as pn

from ..manifest import Manifest

pn.extension()


def build_timewindow_options(manifest: Manifest) -> Dict[str, str]:
    """
    Build a label -> timewindow_str mapping for the time-window select widget.
    Same pattern as in the Forecasts tab.
    """
    tw_strings = getattr(manifest, "time_windows", []) or []
    options: Dict[str, str] = {}
    for tw in tw_strings:
        label = tw
        options[label] = tw
    return options


def build_test_options(manifest: Manifest) -> Dict[str, str]:
    """
    Build a label -> test_name mapping for the test select widget.
    """
    tests: List[Dict[str, Any]] = getattr(manifest, "tests", []) or []
    options: Dict[str, str] = {}
    for t in tests:
        name = t.get("name") or "Unnamed Test"
        options[name] = name
    return options


def index_tests_by_name(manifest: Manifest) -> Dict[str, Dict[str, Any]]:
    """Convenience mapping: test_name -> test_dict."""
    tests: List[Dict[str, Any]] = getattr(manifest, "tests", []) or []
    return {t.get("name"): t for t in tests if t.get("name") is not None}


def build_model_options_for_test(
    manifest: Manifest,
    test_name: Optional[str],
) -> Dict[str, Optional[str]]:
    """
    Build model options for a given test.

    - Always include "All models" (None value) which maps to results_main.
    - If there are per-model figures for this test, add each model by name.
    """
    options: Dict[str, Optional[str]] = {"All models": None}

    if not test_name:
        return options

    res_model: Dict[Tuple[str, str, str], str] = getattr(manifest, "results_model", {}) or {}

    model_names = {
        model_name for (tw_str, t_name, model_name) in res_model.keys() if t_name == test_name
    }

    for m in sorted(model_names):
        options[m] = m

    return options


def resolve_result_figure_path(
    manifest: Manifest,
    timewindow_str: Optional[str],
    test_name: Optional[str],
    model_name: Optional[str],
) -> Optional[Path]:
    """
    Given the current selection, return the absolute Path to the result figure,
    or None if not available.
    """
    if not timewindow_str or not test_name:
        return None

    results_main: Dict[Tuple[str, str], str] = getattr(manifest, "results_main", {}) or {}
    results_model: Dict[Tuple[str, str, str], str] = (
        getattr(manifest, "results_model", {}) or {}
    )

    rel: Optional[str] = None

    if model_name is None:
        rel = results_main.get((timewindow_str, test_name))
    else:
        rel = results_model.get((timewindow_str, test_name, model_name))
        if rel is None:
            rel = results_main.get((timewindow_str, test_name))

    if not rel:
        return None

    app_root = Path(getattr(manifest, "app_root", "."))
    return (app_root / rel).resolve()


def results_overview_block(manifest: Manifest) -> pn.panel:
    """Title block for the Results tab."""
    text = "## Evaluation Results"
    return pn.pane.Markdown(text, sizing_mode="stretch_width")


def build_results_view(manifest: Manifest) -> pn.layout.Panel:
    """
    Build the Evaluation Results tab view.

    """

    test_by_name = index_tests_by_name(manifest)

    tw_options = build_timewindow_options(manifest)
    test_options = build_test_options(manifest)

    initial_tw = next(iter(tw_options.values()), None)
    initial_test = next(iter(test_options.values()), None)
    initial_model_options = build_model_options_for_test(manifest, initial_test)

    timewindow_select = pn.widgets.Select(
        name="Time window",
        options=tw_options,
        value=initial_tw,
        sizing_mode="stretch_width",
    )

    test_select = pn.widgets.Select(
        name="Test",
        options=test_options,
        value=initial_test,
        sizing_mode="stretch_width",
    )

    model_select = pn.widgets.Select(
        name="Model",
        options=initial_model_options,
        value=next(iter(initial_model_options.values()), None),
        sizing_mode="stretch_width",
    )

    test_metadata_pane = pn.pane.Markdown(
        "",
        sizing_mode="stretch_width",
        styles={"font-size": "11px"},
    )

    figure_pane = pn.pane.PNG(
        None,
        sizing_mode="stretch_both",
        align="start",
    )

    def update_test_metadata(test_name: Optional[str]) -> None:
        """Update the descriptive metadata block for the selected test."""
        if not test_name or test_name not in test_by_name:
            test_metadata_pane.object = "_No metadata available for this test._"
            return

        t = test_by_name[test_name]
        lines: List[str] = []
        lines.append("### Test details\n")
        lines.append(f"- **Name:** {t.get('name', '—')}")
        lines.append(f"- **Function:** `{t.get('func', '—')}`")
        ref_model = t.get("ref_model", None)
        if ref_model:
            lines.append(f"- **Reference model:** {ref_model}")
        func_kwargs = t.get("func_kwargs") or {}
        if func_kwargs:
            lines.append("- **Parameters:**")
            for k, v in func_kwargs.items():
                lines.append(f"  - `{k}` = `{v}`")

        test_metadata_pane.object = "\n".join(lines)

    def refresh_model_options(event=None) -> None:
        """
        When the test changes, rebuild the model options list
        (always including 'All models').
        """
        test_name = test_select.value
        model_opts = build_model_options_for_test(manifest, test_name)

        current = model_select.value
        if current not in model_opts.values():
            current = next(iter(model_opts.values()), None)

        model_select.options = model_opts
        model_select.value = current

    def update_figure(event=None) -> None:
        """Update the figure pane based on current selections."""
        tw_str = timewindow_select.value
        test_name = test_select.value
        model_name = model_select.value

        path = resolve_result_figure_path(manifest, tw_str, test_name, model_name)
        if path is None or not path.exists():
            figure_pane.object = None
            figure_pane.alt_text = "No result figure available for this selection."
            return

        figure_pane.object = str(path)
        figure_pane.alt_text = f"Results for {test_name} ({tw_str})"

    def on_test_change(event):
        update_test_metadata(event.new)
        refresh_model_options()
        update_figure()

    test_select.param.watch(on_test_change, "value")
    timewindow_select.param.watch(update_figure, "value")
    model_select.param.watch(update_figure, "value")

    update_test_metadata(initial_test)
    update_figure()

    left_col = pn.Column(
        results_overview_block(manifest),
        pn.layout.Divider(),
        timewindow_select,
        test_select,
        model_select,
        pn.layout.Divider(),
        test_metadata_pane,
        width=380,
    )

    right_col = pn.Column(
        pn.Spacer(height=25),
        figure_pane,
        pn.Spacer(height=25),
        sizing_mode="stretch_both",
    )

    return pn.Row(
        left_col,
        pn.Spacer(width=30),
        right_col,
        sizing_mode="stretch_both",
    )
