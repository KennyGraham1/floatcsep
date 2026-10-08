"""
Collect the inputs of Tutorial K from the global quadtree experiment.

The forecasts (M7.45+ rates per year on multi-resolution quadtree grids) and the
gCMT catalogue come from a local copy of the global experiment. They are copied
here but not tracked by git (see the repository .gitignore), because several of
the forecasts are unpublished research output.

Usage::

    python prepare.py --source /path/to/globalExperiment [--grids N50L11 SN10L11 ...]

Every model is set up on every selected grid (all eight by default), named
``<MODEL>=<GRID>`` as in the global experiment, and ``models.yml`` is rewritten
to match. The source directory is only read.

PPE, EEPASfull and SUP are set up as time-dependent models, a folder with one forecast
per time window. The whole period uses the eight-year forecast of the global
experiment. Each year uses the forecast of its annual experiment for that year, which
reissues PPE and EEPASfull every year from the catalogue before it, and keeps one SUP
baseline (its 2014 forecast). Both use the same parameters, fitted on 1994-2013; only
the catalogue grows from year to year. The other six models are time-independent: one
forecast, scaled to each window.

The global experiment also tested the models on their native 0.1-degree grid
(FULL01, 6.48 million cells) over the whole period, with the same forecasts and
tests. Its results are copied into ``imported/<window>/`` (skip with
``--no-native``), and custom_plots.py shows them next to the quadtree grids;
native_grid.py computes them for every time window, the years included. The
figures that about.md shows in the dashboard's About page (how quadtrees are
built, the aggregation, the forecasts) are copied into ``about/``.
"""

import argparse
import csv
import datetime
import filecmp
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# Brief descriptions, from the global experiment's table of models, and how each varies
# in time (written into models.yml and shown in the dashboard's table of models)
MODELS = {
    "GEAR1": "Log-linear hybrid of smoothed seismicity and geodetic strain; the benchmark. "
    "Published GEFE forecast, time-independent",
    "KJSS": "Kagan-Jackson smoothed seismicity. Published GEFE forecast, time-independent",
    "SHIFT2F_GSRM": "Seismicity from the GSRM 2.1 strain rates. Published GEFE forecast, "
    "time-independent",
    "TEAM": "Tectonic model: SMERF2 combined with a scaled SHIFT2F_GSRM. Published GEFE "
    "forecast, time-independent",
    "WHEEL": "Log-linear hybrid of KJSS and TEAM. Published GEFE forecast, time-independent",
    "EEPASfull": "Every Earthquake a Precursor According to Scale, mixed with PPE. "
    "Refitted with the M>=5.45 PPE as its background (mu 0.41); reissued every year, with "
    "the same parameters, in the annual windows",
    "PPE": "Proximity to Past Earthquakes. Smoothed over M>=5.45 sources since 1918 "
    "(ISC-GEM and gCMT), fitted 1994-2013; reissued every year, with the same parameters, "
    "in the annual windows",
    "SUP": "Spatially uniform Poisson baseline. Fitted before 2014; one rate for every year",
    "GSSGSRM": "The SUP baseline modulated by the GSRM strain-rate alarm. Fitted before "
    "2014, time-independent",
}
# The time-dependent models, with the year of the annual experiment's forecast that each
# year uses: its own (PPE and EEPASfull are reissued every year) or 2014 (SUP's baseline)
TIME_VARYING = {"EEPASfull": None, "PPE": None, "SUP": 2014}
YEARS = range(2014, 2022)
GRIDS = ["N10L11", "N25L11", "N50L11", "N100L11", "SN10L11", "SN25L11", "SN50L11", "SN100L11"]

REGEN = Path("gefe-quadtree_results_2023-03", "regen")
FORECASTS = REGEN / "m745_models"
ANNUAL_FORECASTS = REGEN / "annual_models"  # <year>/<MODEL>=<GRID>.csv
M745_RESULTS = REGEN / "m745_experiment" / "results" / "20230329T235959"
NATIVE_RESULTS = M745_RESULTS / "evaluations"
NATIVE_GRID = "FULL01"
NATIVE_WINDOW = "2014-01-01_2022-01-01"  # the whole testing period, as floatCSEP names it
# The global experiment's test names, as in tests.yml (and the T-test of custom_plots.py)
NATIVE_TESTS = {
    "N": "Poisson N-test",
    "M": "Poisson M-test",
    "S": "Poisson S-test",
    "CL": "Poisson CL-test",
    "T": "Paired T-test",
}
# Figures of about.md, by their name in about/
ABOUT_FIGURES = {
    "fig_quadtree_build.png": M745_RESULTS / "figures" / "fig_quadtree_build.png",
    "aggregation.png": M745_RESULTS / "figures" / "aggregation.png",
    "rate_density_maps.png": M745_RESULTS / "figures" / "rate_density_maps.png",
}
CATALOG = Path("eepasModel", "run", "gcmt_M595_1976_2022.dat")


# The depth range of the experiment (config.yml). floatCSEP filters the test catalogues
# by time, magnitude and region, but not by depth, so the catalogue is limited here.
DEPTH_RANGE = (0.0, 70.0)


def convert_gcmt(source: Path, target: Path) -> tuple:
    """
    gCMT table (yr mo dy hr mn sec lat lon depth Mw) -> pyCSEP ASCII catalogue, keeping
    the events in DEPTH_RANGE. Returns the number of events and the smallest magnitude.
    """
    rows, smallest = 0, float("inf")
    with open(source) as f_in, open(target, "w", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["lon", "lat", "mag", "time_string", "depth", "catalog_id", "event_id"])
        for line in f_in:
            fields = line.split()
            if len(fields) < 10:
                continue
            year, month, day, hour, minute = (int(v) for v in fields[:5])
            seconds = float(fields[5])
            lat, lon, depth, mag = (float(v) for v in fields[6:10])
            if not DEPTH_RANGE[0] <= depth <= DEPTH_RANGE[1]:
                continue
            time = datetime.datetime(year, month, day, hour, minute) + datetime.timedelta(
                seconds=seconds
            )
            event_id = f"gcmt{time:%Y%m%d%H%M%S}"
            writer.writerow(
                [lon, lat, mag, time.strftime("%Y-%m-%dT%H:%M:%S.%f"), depth, -1, event_id]
            )
            rows += 1
            smallest = min(smallest, mag)
    return rows, smallest


def write_models_yml(grids) -> None:
    lines = [
        "# Generated by prepare.py: every model on every grid, named <MODEL>=<GRID>.",
        "# Rates are expected M7.45+ events per year (forecast_unit: 1). PPE, EEPASfull and",
        "# SUP are time-dependent: a folder with one forecast per time window.",
    ]
    for grid in grids:
        lines.append(f"# Quadtree grid {grid}")
        for model, description in MODELS.items():
            name = f"{model}={grid}"
            if model in TIME_VARYING:
                lines += [
                    f"- {name}:",
                    f"    path: models/{name}",
                    "    class: td",
                    "    forecast_type: gridded",
                ]
            else:
                lines += [f"- {name}:", f"    path: models/{name}.csv", "    forecast_unit: 1"]
            lines.append(f"    description: {json.dumps(description, ensure_ascii=False)}")
    (HERE / "models.yml").write_text("\n".join(lines) + "\n")


def write_sources(source: Path) -> dict:
    """
    The global experiment can fill a model's slot from another source, recorded in
    m745_models/<SLOT>_source.json (e.g. PPE from PPE_WU1918P545). The slot keeps its name
    in the forecasts, but its 0.1-degree array is named after the source: models/sources.json
    tells native_grid.py which to read.
    """
    sources = {}
    for path in sorted((source / FORECASTS).glob("*_source.json")):
        spec = json.loads(path.read_text())
        if spec.get("slot") in MODELS and spec.get("source_model"):
            sources[spec["slot"]] = spec["source_model"]
    (HERE / "models").mkdir(exist_ok=True)
    (HERE / "models" / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
    return sources


def copy_native_results(source: Path) -> int:
    """Copies the global experiment's whole-period results on the native 0.1-degree grid.

    They are named as floatCSEP names its results: <test>_<MODEL>=FULL01.json.
    """
    target = HERE / "imported" / NATIVE_WINDOW
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for model in MODELS:
        for key, test in NATIVE_TESTS.items():
            name = f"Poisson_{key}_{model}={NATIVE_GRID}.json"
            if (source / NATIVE_RESULTS / name).is_file():
                shutil.copyfile(
                    source / NATIVE_RESULTS / name,
                    target / f"{test}_{model}={NATIVE_GRID}.json",
                )
                copied += 1
    return copied


def copy_about_figures(source: Path) -> int:
    """Copies the figures shown by about.md, where the global experiment has them."""
    target = HERE / "about"
    target.mkdir(exist_ok=True)
    copied = 0
    for name, path in ABOUT_FIGURES.items():
        if (source / path).is_file():
            shutil.copyfile(source / path, target / name)
            copied += 1
    return copied


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--source", required=True, type=Path, help="global experiment directory"
    )
    parser.add_argument(
        "--grids",
        nargs="+",
        default=GRIDS,
        choices=GRIDS,
        help="quadtree grids (default: all)",
    )
    parser.add_argument(
        "--no-native",
        action="store_true",
        help="do not copy the results on the native 0.1-degree grid",
    )
    args = parser.parse_args(argv)

    source = args.source.expanduser().resolve()
    wanted = [(m, g) for g in args.grids for m in MODELS]
    missing = [source / CATALOG] if not (source / CATALOG).is_file() else []
    sources = [source / FORECASTS / f"{m}={g}.csv" for m, g in wanted]
    sources += [
        source / ANNUAL_FORECASTS / str(TIME_VARYING[m] or year) / f"{m}={g}.csv"
        for m, g in wanted
        if m in TIME_VARYING
        for year in YEARS
    ]
    missing += [path for path in sources if not path.is_file()]
    if missing:
        listing = "\n  ".join(str(p) for p in missing)
        print(f"Missing input files:\n  {listing}", file=sys.stderr)
        return 1

    models_dir = HERE / "models"
    models_dir.mkdir(exist_ok=True)
    updated = []

    def copy(src: Path, dst: Path) -> None:
        """Copies a forecast unless an identical one is there: an unchanged file keeps its
        time, so that only the results of changed forecasts need to be computed again."""
        if not (dst.is_file() and filecmp.cmp(src, dst, shallow=False)):
            shutil.copyfile(src, dst)
            updated.append(dst.name)

    for model, grid in wanted:
        name = f"{model}={grid}"
        if model not in TIME_VARYING:
            copy(source / FORECASTS / f"{name}.csv", models_dir / f"{name}.csv")
            continue
        # One forecast per time window, named as floatCSEP looks for them
        forecasts = models_dir / name / "forecasts"
        forecasts.mkdir(parents=True, exist_ok=True)
        copy(source / FORECASTS / f"{name}.csv", forecasts / f"{name}_{NATIVE_WINDOW}.csv")
        for year in YEARS:
            annual = (
                source / ANNUAL_FORECASTS / str(TIME_VARYING[model] or year) / f"{name}.csv"
            )
            copy(annual, forecasts / f"{name}_{year}-01-01_{year + 1}-01-01.csv")
        (models_dir / f"{name}.csv").unlink(missing_ok=True)  # from an earlier setup
    print(
        f"{len(updated)} forecast files new or changed"
        + (
            f": {', '.join(updated[:6])}" + (" ..." if len(updated) > 6 else "")
            if updated
            else ""
        )
    )
    write_models_yml(args.grids)
    sources = write_sources(source)
    if sources:
        print(
            "Models in a slot from another source: "
            + ", ".join(f"{k} = {v}" for k, v in sources.items())
        )

    events, smallest = convert_gcmt(source / CATALOG, HERE / "catalog.csv")
    print(
        f"Copied {len(MODELS)} models on {len(args.grids)} grid(s) "
        f"({', '.join(args.grids)}) and {events} gCMT events "
        f"(Mw {smallest:g} and above, {DEPTH_RANGE[0]:g}-{DEPTH_RANGE[1]:g} km)."
    )
    figures = copy_about_figures(source)
    print(f"Copied {figures} of the {len(ABOUT_FIGURES)} figures of about.md.")
    if not args.no_native:
        native = copy_native_results(source)
        print(
            f"Copied {native} results on the native 0.1-degree grid ({NATIVE_GRID})."
            if native
            else f"No results on the native grid found in {source / NATIVE_RESULTS}."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
