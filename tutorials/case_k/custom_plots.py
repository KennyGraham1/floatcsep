"""
Post-processing of Tutorial K (``plot_custom`` in config.yml): paired T-tests
against GEAR1 *on the same grid*, and the summary figures of the global
quadtree experiment, ported from its scripts (better_test_plots.py,
eepasModel/run/annual/step5_plots.py and eepasModel/run/quadtree_grid_fig.py).

Models are named ``<MODEL>=<GRID>``. The experiment's longest time window is
the whole testing period; the one-year windows are the annual forecasts.
Written into the results directory:

    <window>/evaluations/Paired T-test_<MODEL>=<GRID>.json
                                    T-test vs GEAR1 on the same grid (floatCSEP result)
    figures/{N,M,S,CL}_heatmap.png  test scores, models x grids (whole period)
    figures/{N,M,S,CL}_facets.png   simulated interval and observation, per grid
    figures/T_ranked.png            information gain vs GEAR1, per model and grid
    figures/annual_consistency.png  N/M/S/CL outcomes by year (primary grid)
    figures/annual_ig_heatmap.png   information gain vs GEAR1 by year (primary grid)
    figures/annual_consistency_native.png, annual_ig_heatmap_native.png
                                    the same on the native 0.1° grid
    figures/annual_counts.png       forecast vs observed events by year (primary grid)
    figures/annual_pooled_ig.png    T-test pooled over the years (primary grid)
    figures/quadtree_grids.png      the quadtree grids
    figures/grid_levels.png         the grids compared: cells per zoom level, cells against N
    figures/quadtree_japan.png      three grids and the native 0.1° lattice around Japan

Results on the models' native 0.1-degree grid (FULL01, 6.48 million cells),
computed by the global experiment for the whole period with the same forecasts
and tests, are copied by prepare.py into imported/. They are stored next to
floatCSEP's own results and shown as a ninth grid in the whole-period figures.
"""

import json
import logging
import os
import re
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from csep.core import poisson_evaluations  # noqa: E402
from matplotlib.collections import LineCollection, PatchCollection  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402
from scipy import stats  # noqa: E402

from floatcsep.evaluation import filter_to_region  # noqa: E402
from floatcsep.utils.helpers import timewindow2str  # noqa: E402

log = logging.getLogger("floatLogger")

REF = "GEAR1"
PRIMARY_GRID = "N50L11"
ALPHA = 0.05
T_TEST = "Paired T-test"
TESTS = {
    "N": "Poisson N-test",
    "M": "Poisson M-test",
    "S": "Poisson S-test",
    "CL": "Poisson CL-test",
    "T": T_TEST,
}
# The models' native 0.1-degree grid (results from imported/, see native_grid.py)
NATIVE = "FULL01"
ORDER = ["GEAR1", "KJSS", "SHIFT2F_GSRM", "TEAM", "WHEEL", "GSSGSRM", "SUP", "PPE", "EEPASfull"]
GRID_ORDER = [
    "N10L11",
    "N25L11",
    "N50L11",
    "N100L11",
    "SN10L11",
    "SN25L11",
    "SN50L11",
    "SN100L11",
]

CONSIST = {
    "N": dict(
        title="N-test (number)",
        xlabel="number of events",
        two_sided=True,
        score=r"$\min(\delta_1,\delta_2)$",
    ),
    "M": dict(
        title="M-test (magnitude)",
        xlabel="log-likelihood",
        two_sided=False,
        score=r"quantile $\gamma$",
    ),
    "S": dict(
        title="S-test (spatial)",
        xlabel="log-likelihood",
        two_sided=False,
        score=r"quantile $\gamma$",
    ),
    "CL": dict(
        title="CL-test (space and magnitude)",
        xlabel="log-likelihood",
        two_sided=False,
        score=r"quantile $\gamma$",
    ),
}

# Validated palette, as in the global experiment's figures
BLUE, RED = "#2a78d6", "#e34948"
NEUTRAL = "#f0efec"
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8983"
GOOD, BAD = "#1baf7a", "#e34948"
PASS, FAIL, TIE = "#1e8449", "#c0392b", "#7f8c8d"
EDGE = "#1b4f72"
ORANGE = "#eb6834"
EQUATOR_KM = 40075.0
# Epicentre of the 2011 Tohoku earthquake: the anchor of the nested quadkeys in quadtree_japan
TOHOKU = (142.37, 38.30)
DIVERGING = LinearSegmentedColormap.from_list("bl_rd", [RED, NEUTRAL, BLUE])
STYLE = {
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK2,
    "text.color": INK,
    "xtick.color": INK2,
    "ytick.color": INK2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "normal",
    "grid.color": "#e6e5e1",
    "grid.linewidth": 0.8,
    "hatch.linewidth": 0.8,
}


class _NumpyEncoder(json.JSONEncoder):
    """As floatCSEP's ResultsRepository.write_result."""

    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


# --------------------------------------------------------------- experiment


def split_name(name):
    model, _, grid = name.partition("=")
    return model, grid or "grid"


def years_between(window):
    return (window[1] - window[0]).days / 365.25


class Layout:
    """Models by (model, grid), the whole-period window and the annual windows."""

    def __init__(self, experiment):
        self.experiment = experiment
        self.run_dir = experiment.registry.abs(experiment.registry.run_dir)
        self.models = {split_name(m.name): m for m in experiment.models}
        names = {m for m, _ in self.models}
        grids = {g for _, g in self.models}
        self.model_names = [m for m in ORDER if m in names] + sorted(names - set(ORDER))
        self.grids = [g for g in GRID_ORDER if g in grids] + sorted(grids - set(GRID_ORDER))
        self.primary = PRIMARY_GRID if PRIMARY_GRID in self.grids else self.grids[0]
        # Grids of the whole-period figures: these, and the native grid once imported
        self.columns = list(self.grids)
        self._regions = {}
        windows = list(experiment.time_windows)
        self.full = max(windows, key=years_between)
        self.annual = [
            w for w in windows if w is not self.full and abs(years_between(w) - 1) < 0.01
        ]

    def region(self, grid):
        """The quadtree region of a grid (from the forecast of one of its models)."""
        if grid not in self._regions:
            model = self.models.get((REF, grid)) or next(
                m for (_, g), m in self.models.items() if g == grid
            )
            self._regions[grid] = model.get_forecast(timewindow2str(self.full)).region
        return self._regions[grid]

    def path(self, window, test, name):
        return os.path.join(
            self.run_dir, timewindow2str(window), "evaluations", f"{test}_{name}.json"
        )

    def load(self, window, test, model, grid):
        path = self.path(window, test, f"{model}={grid}")
        if not os.path.isfile(path):
            return None
        with open(path) as f:
            return json.load(f)

    def result(self, window, key, model, grid):
        return self.load(window, TESTS[key], model, grid)


def same_grid_ttests(layout):
    """Paired T-test of every model against GEAR1 on its own grid, in every window."""
    experiment = layout.experiment
    written = 0
    for window in experiment.time_windows:
        window_str = timewindow2str(window)
        for grid in layout.grids:
            ref = layout.models.get((REF, grid))
            if ref is None:
                continue
            reference = ref.get_forecast(window_str)
            for model in layout.model_names:
                entry = layout.models.get((model, grid))
                if model == REF or entry is None:
                    continue
                forecast = entry.get_forecast(window_str)
                catalog = experiment.catalog_repo.get_test_cat(window_str)
                filter_to_region(catalog, forecast.region)
                catalog.region = forecast.region
                result = poisson_evaluations.paired_t_test(forecast, reference, catalog)
                with open(layout.path(window, T_TEST, entry.name), "w") as f:
                    json.dump(result.to_dict(), f, indent=4, cls=_NumpyEncoder)
                written += 1
    log.info(f"Wrote {written} same-grid paired T-test results")


def import_native_results(layout):
    """
    Results on the native 0.1-degree grid, from imported/<window>/: prepare.py copies
    the global experiment's whole-period results there, and native_grid.py computes
    them for every window. They are stored like floatCSEP's own results.
    """
    copied = 0
    for window in layout.experiment.time_windows:
        source = layout.experiment.registry.abs("imported", timewindow2str(window))
        if not os.path.isdir(source):
            continue
        for name in sorted(os.listdir(source)):
            if name.endswith(f"={NATIVE}.json"):
                target = os.path.join(os.path.dirname(layout.path(window, "", "")), name)
                shutil.copyfile(os.path.join(source, name), target)
                copied += 1
    if os.path.isfile(layout.path(layout.full, TESTS["S"], f"{REF}={NATIVE}")):
        layout.columns.append(NATIVE)
    log.info(f"Imported {copied} results on the native 0.1-degree grid")


def pooled_ttest(layout, model, grid, windows):
    """T-test of model vs GEAR1 on one grid, pooling the target events of `windows`."""
    diffs, count_model, count_ref = [], 0.0, 0.0
    for window in windows:
        window_str = timewindow2str(window)
        forecast = layout.models[(model, grid)].get_forecast(window_str)
        reference = layout.models[(REF, grid)].get_forecast(window_str)
        catalog = layout.experiment.catalog_repo.get_test_cat(window_str)
        filter_to_region(catalog, forecast.region)
        catalog.region = forecast.region
        rates, n_model = forecast.target_event_rates(catalog)
        rates_ref, n_ref = reference.target_event_rates(catalog)
        diffs.extend(np.log(rates) - np.log(rates_ref))
        count_model += n_model
        count_ref += n_ref
    n = len(diffs)
    if n == 0:
        return None
    diffs = np.asarray(diffs)
    ig = (diffs.sum() - (count_model - count_ref)) / n
    if n < 2:
        return {"n": n, "ig": float(ig), "lower": None, "upper": None}
    half = stats.t.ppf(1 - ALPHA / 2, n - 1) * np.std(diffs, ddof=1) / np.sqrt(n)
    return {"n": n, "ig": float(ig), "lower": float(ig - half), "upper": float(ig + half)}


# ------------------------------------------------------------ test verdicts


def score_pass(result, two_sided):
    if two_sided:
        s = min(result["quantile"])
        return s, s >= ALPHA / 2
    q = result["quantile"]
    q = q[0] if isinstance(q, list) else q
    return q, q >= ALPHA


def interval(result, two_sided):
    """(centre, lower, upper, observed, passed), as in better_test_plots.py."""
    obs = result["observed_statistic"]
    td = result["test_distribution"]
    _, passed = score_pass(result, two_sided)
    if isinstance(td, list) and len(td) == 2 and td[0] == "poisson":
        mean = td[1]
        return (
            mean,
            stats.poisson.ppf(ALPHA / 2, mean),
            stats.poisson.ppf(1 - ALPHA / 2, mean),
            obs,
            passed,
        )
    a = np.asarray(td, float)
    centre = np.median(a)
    if two_sided:
        lo, hi = np.percentile(a, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
    else:
        lo, hi = np.percentile(a, 100 * ALPHA), a.max()
    return centre, lo, hi, obs, passed


def period_label(window):
    return f"[{window[0].year}, {window[1].year})"


def grid_label(grid):
    return "0.1° native" if grid == NATIVE else grid.replace("L11", "")


# ------------------------------------------------ whole period: across grids


def heatmap(layout, key, out_dir):
    cfg = CONSIST[key]
    models, grids = layout.model_names, layout.columns
    thr = ALPHA / 2 if cfg["two_sided"] else ALPHA
    scores = np.full((len(models), len(grids)), np.nan)
    passed = np.ones_like(scores, bool)
    for i, m in enumerate(models):
        for k, g in enumerate(grids):
            r = layout.result(layout.full, key, m, g)
            if r:
                scores[i, k], passed[i, k] = score_pass(r, cfg["two_sided"])
    if np.isnan(scores).all():
        return
    cmap = LinearSegmentedColormap.from_list(
        "pf", ["#7b241c", "#c0392b", "#f1948a", "#fdebd0", "#abebc6", "#52be80", "#1e8449"]
    )
    norm = TwoSlopeNorm(vmin=0.0, vcenter=thr, vmax=1.0)
    fig, ax = plt.subplots(figsize=(0.8 * len(grids) + 1.4, 4.1 * len(models) / 9.0 + 0.4))
    im = ax.imshow(scores, cmap=cmap, norm=norm, aspect="auto")
    ax.set_xticks(range(len(grids)), [grid_label(g) for g in grids], fontsize=8.5)
    ax.set_yticks(range(len(models)), models, fontsize=8.5)
    ax.set_xlabel("Evaluation grid", fontsize=9.5, labelpad=6)
    for i in range(len(models)):
        for k in range(len(grids)):
            v = scores[i, k]
            if np.isnan(v):
                continue
            r, g_, b, _ = cmap(norm(v))
            color = "#ffffff" if (0.299 * r + 0.587 * g_ + 0.114 * b) < 0.5 else INK
            ax.text(k, i, f"{v:.2f}", ha="center", va="center", fontsize=8.5, color=color)
            if not passed[i, k]:
                # Rejected cells are hatched and outlined: the verdict is not colour-only.
                ax.add_patch(
                    Rectangle(
                        (k - 0.5, i - 0.5),
                        1,
                        1,
                        fill=False,
                        hatch="///",
                        edgecolor="#ffffff",
                        lw=0,
                        alpha=0.55,
                        zorder=2,
                    )
                )
                ax.add_patch(
                    Rectangle(
                        (k - 0.5, i - 0.5), 1, 1, fill=False, edgecolor=INK, lw=1.6, zorder=3
                    )
                )
    groups = [
        ("catalogue-refined ($N$)", [k for k, g in enumerate(grids) if g.startswith("N")]),
        ("catalogue and strain ($SN$)", [k for k, g in enumerate(grids) if g.startswith("SN")]),
        ("native", [k for k, g in enumerate(grids) if g == NATIVE]),
    ]
    groups = [(label, cols) for label, cols in groups if cols]
    if len(groups) > 1:
        for n, (label, cols) in enumerate(groups):
            ax.text(
                (cols[0] + cols[-1]) / 2, -0.72, label, ha="center", fontsize=8.5, color=INK
            )
            if n > 0:
                ax.axvline(cols[0] - 0.5, color="white", lw=4)
                ax.axvline(cols[0] - 0.5, color=INK, lw=1.2)
    ax.set_xticks(np.arange(-0.5, len(grids), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(models), 1), minor=True)
    ax.grid(which="minor", color="white", lw=1.5)
    ax.tick_params(which="both", length=0)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    cb = fig.colorbar(
        im, ax=ax, fraction=0.03, pad=0.02, ticks=sorted({thr, 0.25, 0.5, 0.75, 1.0})
    )
    cb.set_label(cfg["score"], fontsize=9)
    cb.ax.tick_params(labelsize=8)
    cb.ax.axhline(thr, color=INK, lw=1.5)
    total = int(np.isfinite(scores).sum())
    n_pass = int((passed & np.isfinite(scores)).sum())
    legend = [
        Rectangle(
            (0, 0),
            1,
            1,
            fill=False,
            edgecolor=INK,
            lw=1.6,
            hatch="///",
            label=(
                f"rejected at $\\alpha = 0.05$ (score $< {thr:g}$); {total - n_pass} of {total}"
            ),
        )
    ]
    ax.legend(
        handles=legend,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.26),
        frameon=False,
        fontsize=8.5,
        handlelength=1.6,
        handleheight=1.2,
    )
    ax.set_title(
        f"Poisson {cfg['title']}, $M \\geq 7.45$, {period_label(layout.full)}",
        loc="left",
        fontsize=10.5,
        color=INK,
        pad=22,
    )
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(os.path.join(out_dir, f"{key}_heatmap.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def facets(layout, key, out_dir):
    cfg = CONSIST[key]
    order = layout.model_names[::-1]
    grids = layout.columns
    ncol = 4 if len(grids) % 4 == 0 else min(3, len(grids))
    nrow = int(np.ceil(len(grids) / ncol))
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(4.3 * ncol, 3.9 * nrow * len(order) / 9.0 + 0.9), squeeze=False
    )
    for ax, grid in zip(axes.ravel(), grids):
        for row, m in enumerate(order):
            r = layout.result(layout.full, key, m, grid)
            if not r:
                continue
            c, lo, hi, obs, passed = interval(r, cfg["two_sided"])
            col = PASS if passed else FAIL
            ax.plot(
                [lo - c, hi - c],
                [row, row],
                color="#566573",
                lw=2.0,
                zorder=2,
                solid_capstyle="round",
            )
            for xb in [lo - c, hi - c] if cfg["two_sided"] else [lo - c]:
                ax.plot([xb, xb], [row - 0.16, row + 0.16], color="#566573", lw=2.0, zorder=2)
            ax.scatter([0], [row], marker="s", s=40, color="#34495e", zorder=3)
            ax.scatter(
                [obs - c],
                [row],
                marker="o",
                s=95,
                color=col,
                edgecolor="white",
                linewidth=1.0,
                zorder=4,
            )
        ax.axvline(0, color="#aab7c4", lw=0.8, ls="--", zorder=1)
        ax.set_yticks(range(len(order)), order, fontsize=9.5)
        ax.set_ylim(-0.6, len(order) - 0.4)
        ax.set_title(grid_label(grid), fontsize=12, color=INK, fontweight="bold")
        ax.tick_params(axis="x", labelsize=8.5)
        ax.grid(axis="x", color="#eef2f5", lw=0.8)
    for ax in axes.ravel()[len(grids) :]:
        ax.set_visible(False)
    legend = [
        Line2D(
            [], [], marker="s", color="#34495e", lw=0, markersize=8, label="simulated median"
        ),
        Line2D([], [], color="#566573", lw=2.2, label="95% simulated interval"),
        Line2D(
            [],
            [],
            marker="o",
            color=PASS,
            lw=0,
            markersize=10,
            markeredgecolor="white",
            label="observed statistic, not rejected",
        ),
        Line2D(
            [],
            [],
            marker="o",
            color=FAIL,
            lw=0,
            markersize=10,
            markeredgecolor="white",
            label="observed statistic, rejected",
        ),
    ]
    fig.legend(
        handles=legend,
        loc="lower center",
        ncol=4,
        frameon=False,
        fontsize=11,
        bbox_to_anchor=(0.5, 0.0),
    )
    fig.suptitle(
        f"Poisson {cfg['title']} by evaluation grid, "
        f"$M \\geq 7.45$, {period_label(layout.full)}",
        fontsize=15,
        color=INK,
    )
    fig.supxlabel(
        f"normalized {cfg['xlabel']}  (value − simulated median)", fontsize=11.5, y=0.06
    )
    fig.tight_layout(rect=(0.01, 0.08, 0.99, 0.97))
    fig.savefig(os.path.join(out_dir, f"{key}_facets.png"), dpi=170, bbox_inches="tight")
    plt.close(fig)


def t_ranked(layout, out_dir):
    """One band per model (best mean information gain first), one row per grid."""
    grids = layout.columns
    models = [m for m in layout.model_names if m != REF]
    data = {}
    for m in models:
        for g in grids:
            r = layout.result(layout.full, "T", m, g)
            if r:
                data[(m, g)] = r
    if not data:
        return
    mean_ig = {
        m: np.mean(
            [data[(m, g)]["observed_statistic"] for g in grids if (m, g) in data] or [np.nan]
        )
        for m in models
    }
    models.sort(key=lambda m: -np.nan_to_num(mean_ig[m], nan=-np.inf))
    finite_lo = [
        min(r["test_distribution"])
        for r in data.values()
        if np.all(np.isfinite(r["test_distribution"])) and np.isfinite(r["observed_statistic"])
    ]
    x_floor = (min(finite_lo) - 0.3) if finite_lo else -1.0
    nrow = len(grids)
    fig, ax = plt.subplots(figsize=(7.4, 0.135 * nrow * len(models) + 1.5))
    ax.axvline(0, color=INK, lw=1.2, zorder=1)
    n_better = n_worse = 0
    centres = []
    for b, m in enumerate(models):
        y0 = b * (nrow + 1.5)
        centres.append(y0 + (nrow - 1) / 2)
        if b % 2 == 1:
            ax.axhspan(y0 - 0.8, y0 + nrow - 0.2, color="#f3f4f6", zorder=0, lw=0)
        for row, g in enumerate(grids):
            r = data.get((m, g))
            if not r:
                continue
            ig = r["observed_statistic"]
            lo, hi = sorted(r["test_distribution"])
            y = y0 + row
            finite = np.isfinite(ig) and np.isfinite(lo) and np.isfinite(hi)
            if finite and lo > 0:
                col, fill = PASS, PASS
                n_better += 1
            elif (finite and hi < 0) or not finite:
                col, fill = FAIL, FAIL
                n_worse += 1
            else:
                col, fill = TIE, "white"
            marker = "D" if g == NATIVE else "o"
            if finite:
                ax.plot([lo, hi], [y, y], color=col, lw=1.4, zorder=2, solid_capstyle="butt")
                ax.scatter(
                    [ig],
                    [y],
                    s=26,
                    marker=marker,
                    facecolor=fill,
                    edgecolor=col,
                    lw=1.1,
                    zorder=3,
                )
            else:
                ax.scatter(
                    [x_floor],
                    [y],
                    s=26,
                    marker=marker,
                    facecolor="none",
                    edgecolor=FAIL,
                    lw=1.2,
                    zorder=3,
                )
            if b % 2 == 0:
                ax.text(
                    1.005,
                    y,
                    grid_label(g),
                    transform=ax.get_yaxis_transform(),
                    fontsize=7,
                    color="#555555",
                    va="center",
                    ha="left",
                )
    ax.set_yticks(centres, [f"{m}\nmean {mean_ig[m]:+.3f}" for m in models], fontsize=8.5)
    ax.invert_yaxis()
    ax.set_ylim(len(models) * (nrow + 1.5) - 1.5, -1.0)
    ax.set_xlabel(
        "Information gain per earthquake against GEAR1 on the same grid "
        "(nats; 95% confidence interval)",
        fontsize=9,
    )
    ax.tick_params(axis="x", labelsize=8.5)
    ax.grid(axis="x", color="#e5e8eb", lw=0.8, zorder=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0)
    legend = [
        Line2D(
            [],
            [],
            marker="o",
            color=TIE,
            markerfacecolor="white",
            lw=1.4,
            label="interval includes zero",
        ),
        Line2D(
            [],
            [],
            marker="o",
            color=FAIL,
            markerfacecolor=FAIL,
            lw=1.4,
            label=f"interval below zero ({n_worse})",
        ),
    ]
    if n_better:
        legend.append(
            Line2D(
                [],
                [],
                marker="o",
                color=PASS,
                markerfacecolor=PASS,
                lw=1.4,
                label=f"interval above zero ({n_better})",
            )
        )
    if NATIVE in grids:
        legend.append(
            Line2D(
                [],
                [],
                marker="D",
                color=INK2,
                markerfacecolor="white",
                lw=0,
                label="native 0.1° grid (diamonds)",
            )
        )
    ax.legend(
        handles=legend,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.05),
        ncol=2,
        fontsize=8,
        frameon=False,
    )
    ax.set_title(
        f"Paired T-test against GEAR1, $M \\geq 7.45$, {period_label(layout.full)}\n"
        f"{len(layout.grids)} quadtree grids for each model"
        + (" and the native 0.1° grid" if NATIVE in grids else ""),
        loc="left",
        fontsize=9.5,
        color=INK,
    )
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "T_ranked.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------- annual: primary grid


def annual_consistency(layout, out_dir, grid=None, suffix=""):
    grid, models = grid or layout.primary, layout.model_names
    years = [str(w[0].year) for w in layout.annual]
    fig, axes = plt.subplots(
        2, 2, figsize=(8.6, 0.62 * len(models) + 2.6), sharey=True, sharex=True
    )
    axes = axes.ravel()
    cmap = LinearSegmentedColormap.from_list("pf", [BAD, GOOD])
    for ax, key in zip(axes, ("N", "M", "S", "CL")):
        mat = np.full((len(models), len(years)), np.nan)
        for i, m in enumerate(models):
            for j, window in enumerate(layout.annual):
                r = layout.result(window, key, m, grid)
                if r:
                    mat[i, j] = 1.0 if score_pass(r, key == "N")[1] else 0.0
        ax.imshow(mat, cmap=cmap, vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(np.arange(len(years)), years, rotation=90, fontsize=8.5)
        ax.set_xticks(np.arange(len(years) + 1) - 0.5, minor=True)
        ax.set_yticks(np.arange(len(models) + 1) - 0.5, minor=True)
        ax.grid(which="minor", color="white", lw=2)
        ax.tick_params(which="minor", length=0)
        n_fail = int(np.nansum(mat == 0))
        ax.set_title(f"{key}-test  ({n_fail} failure{'' if n_fail == 1 else 's'})", loc="left")
        for i in range(len(models)):
            for j in range(len(years)):
                glyph = "?" if np.isnan(mat[i, j]) else ("+" if mat[i, j] == 1.0 else "×")
                ax.text(
                    j,
                    i,
                    glyph,
                    ha="center",
                    va="center",
                    fontsize=10,
                    color="white" if not np.isnan(mat[i, j]) else INK2,
                )
    for ax in (axes[0], axes[2]):
        ax.set_yticks(np.arange(len(models)), models, fontsize=8.5)
    fig.suptitle(
        "Consistency test outcomes by forecast year: "
        f"'+' not rejected, '×' rejected at α = {ALPHA} (grid {grid_label(grid)})",
        x=0.01,
        ha="left",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(os.path.join(out_dir, f"annual_consistency{suffix}.png"), dpi=170)
    plt.close(fig)


def annual_ig_heatmap(layout, out_dir, grid=None, suffix=""):
    grid = grid or layout.primary
    rows = [m for m in layout.model_names if m != REF]
    years = [str(w[0].year) for w in layout.annual]
    mat = np.full((len(rows), len(years)), np.nan)
    for i, m in enumerate(rows):
        for j, window in enumerate(layout.annual):
            r = layout.result(window, "T", m, grid)
            if r and r.get("observed_statistic") is not None:
                mat[i, j] = r["observed_statistic"]
    if np.isnan(mat).all():
        return
    lim = float(np.nanpercentile(np.abs(mat), 90)) or 1.0
    observed = []
    for window in layout.annual:
        r = layout.result(window, "N", REF, grid)
        observed.append(int(r["observed_statistic"]) if r else 0)
    fig, ax = plt.subplots(figsize=(0.78 * len(years) + 2.4, 0.42 * len(rows) + 2.0))
    im = ax.imshow(
        mat, cmap=DIVERGING, aspect="auto", norm=TwoSlopeNorm(vmin=-lim, vcenter=0, vmax=lim)
    )
    ax.set_xticks(np.arange(len(years)), [f"{y}\n({n})" for y, n in zip(years, observed)])
    ax.set_yticks(np.arange(len(rows)), rows)
    ax.set_xticks(np.arange(len(years) + 1) - 0.5, minor=True)
    ax.set_yticks(np.arange(len(rows) + 1) - 0.5, minor=True)
    ax.grid(which="minor", color="white", lw=2)
    ax.tick_params(which="minor", length=0)
    for i in range(len(rows)):
        for j in range(len(years)):
            if np.isfinite(mat[i, j]):
                ax.text(
                    j,
                    i,
                    f"{mat[i, j]:+.2f}".replace("-0.00", "0.00"),
                    ha="center",
                    va="center",
                    fontsize=8.5,
                    color="white" if abs(mat[i, j]) > 0.55 * lim else INK,
                )
    ax.set_title(
        f"Information gain per earthquake against {REF} by forecast year "
        f"(grid {grid_label(grid)})\n"
        f"target events per year in brackets; colour scale saturates at ±{lim:.1f}",
        loc="left",
    )
    fig.colorbar(
        im,
        ax=ax,
        shrink=0.8,
        extend="both",
        label=f"information gain per earthquake against {REF}",
    )
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, f"annual_ig_heatmap{suffix}.png"), dpi=170)
    plt.close(fig)


def annual_counts(layout, out_dir):
    grid, models = layout.primary, layout.model_names
    years = [str(w[0].year) for w in layout.annual]
    observed = []
    for window in layout.annual:
        r = layout.result(window, "N", models[0], grid)
        observed.append(r["observed_statistic"] if r else np.nan)
    ncol = 5
    nrow = int(np.ceil(len(models) / ncol))
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(2.55 * ncol, 2.15 * nrow), sharex=True, sharey=True, squeeze=False
    )
    for ax, m in zip(axes.ravel(), models):
        expected = []
        for window in layout.annual:
            r = layout.result(window, "N", m, grid)
            # The N-test stores the forecast count as ("poisson", expected count).
            expected.append(r["test_distribution"][1] if r else np.nan)
        ax.bar(years, observed, color=NEUTRAL, edgecolor="#d8d7d2", zorder=1, label="observed")
        ax.plot(
            years,
            expected,
            "-o",
            color=BLUE,
            lw=2,
            ms=5,
            zorder=3,
            markeredgecolor="white",
            markeredgewidth=1.2,
            label="forecast",
        )
        ax.set_title(m, loc="left")
        ax.grid(axis="y", zorder=0)
        ax.set_axisbelow(True)
    for ax in axes.ravel()[len(models) :]:
        ax.set_visible(False)
    for ax in axes[-1]:
        ax.tick_params(axis="x", rotation=90)
    axes.ravel()[0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.suptitle(
        f"Forecast count vs observed M7.45+ events per year (grid {grid})",
        x=0.01,
        ha="left",
        fontweight="bold",
    )
    fig.supylabel("events per year", fontsize=9, color=INK2)
    fig.tight_layout(rect=(0.012, 0, 1, 0.96))
    fig.savefig(os.path.join(out_dir, "annual_counts.png"), dpi=170)
    plt.close(fig)


def annual_pooled_ig(layout, out_dir):
    grid = layout.primary
    if (REF, grid) not in layout.models:
        return
    rows = []
    for m in layout.model_names:
        if m == REF or (m, grid) not in layout.models:
            continue
        r = pooled_ttest(layout, m, grid, layout.annual)
        if r:
            rows.append((r["ig"], m, r))
    if not rows:
        return
    rows.sort()
    fig, ax = plt.subplots(figsize=(7.2, 0.42 * len(rows) + 1.9))
    ax.axvline(0, color=MUTED, lw=1.2, zorder=1)
    for i, (ig, _, r) in enumerate(rows):
        sig = r["lower"] is not None and not (r["lower"] <= 0 <= r["upper"])
        col = (BLUE if ig > 0 else RED) if sig else MUTED
        if r["lower"] is not None:
            ax.plot(
                [r["lower"], r["upper"]],
                [i, i],
                color=col,
                lw=2,
                solid_capstyle="round",
                zorder=2,
            )
        ax.plot(
            [ig],
            [i],
            "o",
            ms=8,
            color=col,
            zorder=3,
            markerfacecolor=col if sig else "white",
            markeredgewidth=1.5,
        )
        ax.annotate(
            f"{ig:+.2f}",
            (ig, i),
            textcoords="offset points",
            xytext=(8 if abs(ig) < 0.1 else 0, 10),
            ha="left" if abs(ig) < 0.1 else "center",
            fontsize=8,
            color=INK,
        )
    ax.set_yticks(np.arange(len(rows)), [m for _, m, _ in rows])
    ax.set_xlabel(f"Information gain per earthquake against {REF}")
    ax.set_title(
        f"Pooled information gain against {REF}\n"
        f"{len(layout.annual)} annual forecasts, N = {rows[0][2]['n']} events, grid {grid}",
        loc="left",
        fontsize=10,
    )
    ax.grid(axis="x", zorder=0)
    ax.set_axisbelow(True)
    fig.text(
        0.01,
        0.005,
        "Filled: 95% interval excludes zero.  Open, grey: interval includes zero.",
        fontsize=8,
        color=INK2,
    )
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(os.path.join(out_dir, "annual_pooled_ig.png"), dpi=170)
    plt.close(fig)


# ----------------------------------------------------------- the grids


def quadtree_grids(layout, out_dir):
    """Gallery of the grids on Pacific-centred Robinson maps, with their cell counts."""
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
    except ImportError:
        log.warning("cartopy is not installed; skipping quadtree_grids.png")
        return
    grids = layout.grids
    ncol = 3 if len(grids) > 4 else len(grids)
    nrow = int(np.ceil(len(grids) / ncol))
    fig = plt.figure(figsize=(7.4, 1.75 * nrow + 0.3))
    for i, grid in enumerate(grids):
        region = layout.region(grid)
        bounds = np.asarray(region.bounds)
        levels = [len(q) for q in region.quadkeys]
        ax = fig.add_subplot(nrow, ncol, i + 1, projection=ccrs.Robinson(central_longitude=180))
        try:
            ax.add_feature(cfeature.LAND, facecolor="#efece6", zorder=0)
            ax.add_feature(cfeature.COASTLINE, linewidth=0.25, edgecolor="#7a7a7a")
        except Exception:  # Natural Earth data unavailable offline
            pass
        ax.set_global()
        ax.spines["geo"].set_linewidth(0.6)
        rects = [Rectangle((w, s), e - w, n - s) for w, s, e, n in bounds]
        ax.add_collection(
            PatchCollection(
                rects,
                transform=ccrs.PlateCarree(),
                facecolor="none",
                edgecolor=EDGE,
                linewidth=0.13,
            )
        )
        kind = (
            "catalogue + strain-rate refined" if grid.startswith("SN") else "catalogue-refined"
        )
        ax.set_title(
            f"({'abcdefghij'[i]}) {grid}: {len(bounds):,} cells\n"
            f"{kind}, levels {min(levels)}–{max(levels)}",
            fontsize=7.5,
            loc="left",
        )
    fig.tight_layout()
    fig.savefig(
        os.path.join(out_dir, "quadtree_grids.png"),
        dpi=250,
        bbox_inches="tight",
        pad_inches=0.03,
    )
    plt.close(fig)


def grid_levels(layout, out_dir):
    """The grids compared: how many cells each has at each zoom level, and in all."""
    grids = layout.grids
    counts = {
        g: np.bincount([len(k) for k in layout.region(g).quadkeys], minlength=12) for g in grids
    }
    levels = [z for z in range(1, 12) if any(counts[g][z] for g in grids)]
    table = np.array([[counts[g][z] for z in levels] for g in grids], dtype=float)
    totals = table.sum(axis=1)

    fig, (ax, ax2) = plt.subplots(
        1,
        2,
        figsize=(11.4, 0.42 * len(grids) + 2.0),
        gridspec_kw={"width_ratios": [3.2, 1.2], "wspace": 0.3},
    )
    shown = np.where(table > 0, np.log10(np.maximum(table, 1)), np.nan)
    vmax = np.nanmax(shown)
    cmap = LinearSegmentedColormap.from_list("cells", ["#eaf2fc", BLUE, "#0b2f5c"])
    ax.imshow(shown, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")
    for i in range(len(grids)):
        for j in range(len(levels)):
            if table[i, j] > 0:
                color = "white" if shown[i, j] > 0.55 * vmax else INK
                ax.text(
                    j,
                    i,
                    f"{int(table[i, j]):,}",
                    ha="center",
                    va="center",
                    fontsize=8,
                    color=color,
                )
        ax.text(
            len(levels) - 0.3,
            i,
            f"{int(totals[i]):,}",
            ha="left",
            va="center",
            fontsize=8.5,
            fontweight="bold",
            color=INK,
        )
    ax.text(
        len(levels) - 0.3, -0.65, "all cells", ha="left", va="bottom", fontsize=8, color=INK2
    )
    ax.set_xticks(
        range(len(levels)), [f"L{z}\n{EQUATOR_KM / 2**z:,.0f}" for z in levels], fontsize=7.5
    )
    ax.set_yticks(range(len(grids)), [grid_label(g) for g in grids], fontsize=8.5)
    ax.set_xticks(np.arange(-0.5, len(levels), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(grids), 1), minor=True)
    ax.grid(which="minor", color="white", lw=1.5)
    ax.grid(which="major", visible=False)
    n_catalogue = sum(1 for g in grids if not g.startswith("SN"))
    if 0 < n_catalogue < len(grids):
        ax.axhline(n_catalogue - 0.5, color=INK, lw=1.2)
    ax.tick_params(which="both", length=0)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_xlabel("zoom level, and the width of its cells at the equator (km)", fontsize=8.5)
    ax.set_title("(a) Cells at each zoom level", loc="left", fontsize=10, color=INK)
    if NATIVE in layout.columns:
        ax.text(
            0,
            -0.165,
            "The results are also shown on the models' native grid: a regular 0.1° lattice of "
            "6,480,000 cells, 11 km wide at the equator.",
            transform=ax.transAxes,
            fontsize=8,
            color=INK2,
            va="top",
        )

    for prefix, color, name in (
        ("N", BLUE, "catalogue ($N$)"),
        ("SN", ORANGE, "catalogue and strain ($SN$)"),
    ):
        points = []
        for i, grid in enumerate(grids):
            match = re.fullmatch(r"(S?N)(\d+)L\d+", grid)
            if match and match.group(1) == prefix:
                points.append((int(match.group(2)), totals[i]))
        if points:
            x, y = zip(*sorted(points))
            ax2.plot(
                x,
                y,
                "-o",
                color=color,
                lw=2,
                ms=6,
                markeredgecolor="white",
                mew=1.2,
                label=name,
            )
    ax2.set_xscale("log")
    ax2.set_yscale("log")
    ax2.set_xticks([10, 25, 50, 100], ["10", "25", "50", "100"])
    ax2.set_yticks([1000, 2000, 5000, 10000], ["1,000", "2,000", "5,000", "10,000"])
    ax2.minorticks_off()
    ax2.grid(True)
    ax2.set_xlabel("$N$, the most points a cell may hold", fontsize=8.5)
    ax2.legend(frameon=False, fontsize=8, loc="lower left")
    ax2.set_title("(b) Cells against $N$", loc="left", fontsize=10, color=INK)
    fig.savefig(os.path.join(out_dir, "grid_levels.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def quadtree_japan(layout, out_dir):
    """Cells of three grids around Japan, and how a cell's quadkey extends its parents'."""
    try:
        import cartopy.crs as ccrs
        import cartopy.feature as cfeature
        import mercantile
    except ImportError:
        log.warning("cartopy or mercantile is not installed; skipping quadtree_japan.png")
        return
    from matplotlib.cm import ScalarMappable
    from matplotlib.colors import Normalize

    west, east, south, north = 126.0, 150.0, 26.0, 47.0
    grids = [g for g in ("N10L11", "N50L11", "SN10L11") if g in layout.grids] or layout.grids[
        :3
    ]
    cmap = LinearSegmentedColormap.from_list("levels", ["#f4f8fd", "#9cc3ee", BLUE, "#0b2f5c"])
    norm = Normalize(vmin=2, vmax=11)
    native = NATIVE in layout.columns
    n_panels = len(grids) + native
    ncol = 2 if n_panels == 4 else n_panels
    nrow = int(np.ceil(n_panels / ncol))
    fig = plt.figure(figsize=(3.9 * ncol + 0.6, 4.4 * nrow))
    axes = []
    for i, grid in enumerate(grids):
        ax = fig.add_subplot(nrow, ncol, i + 1, projection=ccrs.Mercator())
        ax.set_extent((west, east, south, north), crs=ccrs.PlateCarree())
        region = layout.region(grid)
        bounds = np.asarray(region.bounds)
        levels = np.array([len(k) for k in region.quadkeys])
        inside = (
            (bounds[:, 2] > west)
            & (bounds[:, 0] < east)
            & (bounds[:, 3] > south)
            & (bounds[:, 1] < north)
        )
        cells = PatchCollection(
            [Rectangle((w, s), e - w, n - s) for w, s, e, n in bounds[inside]],
            transform=ccrs.PlateCarree(),
            cmap=cmap,
            norm=norm,
            edgecolor="#123a63",
            linewidth=0.3,
        )
        cells.set_array(levels[inside])
        ax.add_collection(cells)
        try:
            ax.add_feature(cfeature.COASTLINE, linewidth=0.6, edgecolor="#262626")
        except Exception:  # Natural Earth data unavailable offline
            pass
        ax.spines["geo"].set_linewidth(0.6)
        ax.set_title(
            f"{grid}: {int(inside.sum()):,} cells in view", loc="left", fontsize=9.5, color=INK
        )
        axes.append(ax)

        if grid == "N50L11":
            # The cell holding the Tohoku epicentre, and two of the tiles it was split from
            keys = set(region.quadkeys)
            key = mercantile.quadkey(mercantile.tile(*TOHOKU, 11))
            leaf = next((key[:z] for z in range(11, 0, -1) if key[:z] in keys), None)
            if leaf:
                chain = sorted({max(1, len(leaf) - 4), max(1, len(leaf) - 2), len(leaf)})
                for n_tile, level in enumerate(chain):
                    b = mercantile.bounds(mercantile.quadkey_to_tile(leaf[:level]))
                    is_leaf = level == len(leaf)
                    ax.add_patch(
                        Rectangle(
                            (b.west, b.south),
                            b.east - b.west,
                            b.north - b.south,
                            transform=ccrs.PlateCarree(),
                            fill=False,
                            edgecolor=INK,
                            linewidth=1.6 if is_leaf else 1.1,
                            linestyle="-" if is_leaf else "--",
                            zorder=5,
                        )
                    )
                    # Tags: outer tile at its top-left corner, middle at its bottom-left,
                    # the cell itself beside it
                    if is_leaf:
                        x, y, ha, va = b.east + 0.35, (b.south + b.north) / 2, "left", "center"
                    elif n_tile == 0:
                        x, y, ha, va = b.west + 0.25, b.north - 0.25, "left", "top"
                    else:
                        x, y, ha, va = b.west + 0.2, b.south + 0.2, "left", "bottom"
                    ax.text(
                        x,
                        y,
                        f"L{level}",
                        transform=ccrs.PlateCarree(),
                        ha=ha,
                        va=va,
                        fontsize=7.5,
                        fontweight="bold",
                        color=INK,
                        zorder=6,
                        bbox=dict(
                            boxstyle="round,pad=0.15",
                            facecolor="white",
                            edgecolor="none",
                            alpha=0.85,
                        ),
                    )
                keys = "\n".join(f"L{level:<2} {leaf[:level]}" for level in chain)
                ax.text(
                    0.03,
                    0.97,
                    f"Tohoku 2011 epicentre:\n{keys}",
                    transform=ax.transAxes,
                    ha="left",
                    va="top",
                    fontsize=7.5,
                    family="monospace",
                    color=INK,
                    zorder=6,
                    bbox=dict(
                        boxstyle="round,pad=0.35",
                        facecolor="white",
                        edgecolor="none",
                        alpha=0.92,
                    ),
                )
    if native:
        # The models' native grid: a regular 0.1-degree lattice, finer than any quadtree cell
        ax = fig.add_subplot(nrow, ncol, n_panels, projection=ccrs.Mercator())
        ax.set_extent((west, east, south, north), crs=ccrs.PlateCarree())
        lons = np.arange(west, east + 1e-9, 0.1)
        lats = np.arange(south, north + 1e-9, 0.1)
        lattice = [[(x, south), (x, north)] for x in lons] + [
            [(west, y), (east, y)] for y in lats
        ]
        ax.add_collection(
            LineCollection(
                lattice, transform=ccrs.PlateCarree(), colors="#123a63", linewidths=0.12
            )
        )
        try:
            ax.add_feature(cfeature.COASTLINE, linewidth=0.6, edgecolor="#262626")
        except Exception:  # Natural Earth data unavailable offline
            pass
        ax.spines["geo"].set_linewidth(0.6)
        ax.set_title(
            f"0.1° native: {(len(lons) - 1) * (len(lats) - 1):,} cells in view",
            loc="left",
            fontsize=9.5,
            color=INK,
        )
        axes.append(ax)
    fig.colorbar(
        ScalarMappable(norm=norm, cmap=cmap),
        ax=axes,
        fraction=0.02,
        pad=0.02,
        ticks=range(2, 12),
        label="zoom level of the quadtree cells",
    )
    fig.savefig(os.path.join(out_dir, "quadtree_japan.png"), dpi=200, bbox_inches="tight")
    plt.close(fig)


def main(experiment):
    layout = Layout(experiment)
    out_dir = os.path.join(layout.run_dir, "figures")
    os.makedirs(out_dir, exist_ok=True)

    same_grid_ttests(layout)
    import_native_results(layout)
    with plt.rc_context(STYLE):
        for key in CONSIST:
            heatmap(layout, key, out_dir)
            facets(layout, key, out_dir)
        t_ranked(layout, out_dir)
        if layout.annual:
            annual_consistency(layout, out_dir)
            annual_ig_heatmap(layout, out_dir)
            if all(
                layout.result(w, "S", REF, NATIVE) for w in layout.annual
            ):  # native_grid.py has run
                annual_consistency(layout, out_dir, NATIVE, "_native")
                annual_ig_heatmap(layout, out_dir, NATIVE, "_native")
            annual_counts(layout, out_dir)
            annual_pooled_ig(layout, out_dir)
        quadtree_grids(layout, out_dir)
        grid_levels(layout, out_dir)
        quadtree_japan(layout, out_dir)
    log.info(f"Summary figures written to {out_dir}")
