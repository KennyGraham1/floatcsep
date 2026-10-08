"""
Test the forecasts on the models' native 0.1-degree grid (FULL01) in every time
window of Tutorial K, for custom_plots.py to show next to the quadtree grids.

The global experiment keeps its 0.1-degree forecasts (expected M7.45+ events per year
in 6.48 million cells and 16 magnitude bins) as .npy arrays: the eight-year forecasts
of the nine models, and the annual experiment's forecasts of PPE and EEPASfull for each
year and of SUP for 2014. As in models.yml (see prepare.py), the whole period uses the
eight-year forecasts, and each year the annual ones for the time-dependent models. Run,
after ``floatcsep run config.yml`` (the test catalogues come from its results)::

    python native_grid.py --forecasts /work/kennyg/eepas_spliced_shm_fullgrid_cache \
        --annual-forecasts /work/kennyg/eepas_annual/native_cache

then ``floatcsep plot config.yml`` to add the results to the figures. The arrays are
read where they are, not copied. Written:

    imported/<window>/<test>_<MODEL>=FULL01.json   the results, as floatCSEP names them
    imported/<window>/native_target_rates.json     each model's rates at the target events,
                                                   for the T-test pooled over the years
    external_forecasts.json                        where the arrays are, for the dashboard's
                                                   forecast maps

The tests are those of tests.yml, with their settings, plus the paired T-test
against GEAR1 on the same grid, as on the quadtree grids. pyCSEP's S- and CL-tests
clear and rescan the whole forecast in every simulation (104 million bins for the
CL-test), so here they draw the same random numbers and sum the same terms, but only
over the sampled bins, which gives the same results in seconds (the approach of the
global experiment's fast_poisson.py).
"""

import argparse
import itertools
import json
import logging
import os
import sys
import time

import numpy
from csep.core import poisson_evaluations
from csep.core.forecasts import GriddedForecast
from csep.core.regions import CartesianGrid2D, compute_vertices
from csep.models import EvaluationResult, Polygon
from csep.utils.stats import poisson_joint_log_likelihood_ndarray

from floatcsep.experiment import Experiment
from floatcsep.utils.helpers import timewindow2str

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prepare import NATIVE_WINDOW, TIME_VARYING  # noqa: E402  (the models' time dependence)

HERE = os.path.dirname(os.path.abspath(__file__))
GRID = "FULL01"
REF = "GEAR1"
MODELS = [
    "GEAR1",
    "KJSS",
    "SHIFT2F_GSRM",
    "TEAM",
    "WHEEL",
    "EEPASfull",
    "PPE",
    "SUP",
    "GSSGSRM",
]
T_TEST = "Paired T-test"
DH = 0.1


class _NumpyEncoder(json.JSONEncoder):
    """As floatCSEP's ResultsRepository.write_result."""

    def default(self, obj):
        if isinstance(obj, numpy.integer):
            return int(obj)
        if isinstance(obj, numpy.floating):
            return float(obj)
        if isinstance(obj, numpy.ndarray):
            return obj.tolist()
        return json.JSONEncoder.default(self, obj)


def native_region(magnitudes):
    """The global 0.1-degree grid, in the cell order of the arrays (longitude-major)."""
    lons = numpy.arange(-180.0, 180, DH)
    lats = numpy.arange(-90, 90, DH)
    polygons = [Polygon(b) for b in compute_vertices(itertools.product(lons, lats), DH)]
    region = CartesianGrid2D(polygons, DH, name=GRID)
    region.magnitudes = magnitudes
    return region


def likelihood_test(
    forecast_data,
    observed_data,
    num_simulations=1000,
    seed=None,
    use_observed_counts=True,
    normalize_likelihood=False,
):
    """pyCSEP 0.8's _poisson_likelihood_test, over the sampled bins only.

    The same seeded random numbers are placed with the same searchsorted, and the
    same terms are summed in the same ascending-bin order, so the results are the
    numbers pyCSEP returns.
    """
    if seed is not None:
        numpy.random.seed(seed)
    flat = forecast_data.ravel()
    sampling_weights = numpy.cumsum(flat) / numpy.sum(forecast_data)
    n_obs = numpy.sum(observed_data)
    n_fore = numpy.sum(forecast_data)
    expected_forecast_count = numpy.sum(forecast_data)
    log_bin_expectations = numpy.log(flat)
    if use_observed_counts and normalize_likelihood:
        scale = n_obs / n_fore
        expected_forecast_count = int(n_obs)
        log_bin_expectations = numpy.log(flat * scale)

    target_idx = numpy.nonzero(observed_data.ravel())
    observed_data_nonzero = observed_data.ravel()[target_idx]
    target_event_forecast = log_bin_expectations[target_idx] * observed_data_nonzero

    simulated_ll = []
    for _ in range(num_simulations):
        if use_observed_counts:
            n_events = int(n_obs)
        else:
            n_events = int(numpy.random.poisson(expected_forecast_count))
        points = numpy.searchsorted(sampling_weights, numpy.random.rand(n_events), side="right")
        # pyCSEP's nonzero() of the simulated counts: ascending bins, float64 counts
        bins, counts = numpy.unique(points, return_counts=True)
        counts = counts.astype(numpy.float64)
        simulated_ll.append(
            poisson_joint_log_likelihood_ndarray(
                log_bin_expectations[bins] * counts, counts, expected_forecast_count
            )
        )
    obs_ll = poisson_joint_log_likelihood_ndarray(
        target_event_forecast, observed_data_nonzero, expected_forecast_count
    )
    qs = numpy.sum(simulated_ll <= obs_ll) / num_simulations
    return qs, obs_ll, simulated_ll


def self_check():
    """Checks, on a small random forecast, that likelihood_test still gives pyCSEP's numbers.

    It relies on pyCSEP's internals (the global random generator, the order of the
    sums), so a pyCSEP upgrade could change them without any error.
    """
    from csep.core.poisson_evaluations import _poisson_likelihood_test

    rng = numpy.random.default_rng(1)
    forecast = rng.gamma(0.5, 1e-3, size=(400, 5))
    observed = numpy.zeros_like(forecast)
    observed.ravel()[rng.choice(forecast.size, size=6, replace=False)] = [1, 1, 2, 1, 1, 3]
    for normalize in (True, False):
        options = dict(
            num_simulations=300,
            seed=7,
            use_observed_counts=True,
            normalize_likelihood=normalize,
        )
        expected = _poisson_likelihood_test(forecast, observed, verbose=False, **options)
        found = likelihood_test(forecast, observed, **options)
        if not (
            expected[0] == found[0]
            and expected[1] == found[1]
            and numpy.array_equal(expected[2], found[2])
        ):
            raise RuntimeError(
                "The fast likelihood test no longer reproduces pyCSEP's: check native_grid.py "
                "against this pyCSEP version."
            )


def _likelihood_result(name, forecast, catalog, qs, obs_ll, simulated_ll):
    result = EvaluationResult()
    result.test_distribution = simulated_ll
    result.name = name
    result.observed_statistic = obs_ll
    result.quantile = qs
    result.sim_name = forecast.name
    result.obs_name = catalog.name
    result.status = "normal"
    result.min_mw = numpy.min(forecast.magnitudes)
    return result


def spatial_test(forecast, catalog, observed, num_simulations=1000, seed=None):
    """pyCSEP's spatial_test; `observed` is catalog.spatial_counts()."""
    qs, obs_ll, sims = likelihood_test(
        forecast.spatial_counts(),
        observed,
        num_simulations,
        seed,
        use_observed_counts=True,
        normalize_likelihood=True,
    )
    return _likelihood_result("Poisson S-Test", forecast, catalog, qs, obs_ll, sims)


def conditional_likelihood_test(forecast, catalog, observed, num_simulations=1000, seed=None):
    """pyCSEP's conditional_likelihood_test; `observed`: catalog.spatial_magnitude_counts()."""
    qs, obs_ll, sims = likelihood_test(
        forecast.data,
        observed,
        num_simulations,
        seed,
        use_observed_counts=True,
        normalize_likelihood=False,
    )
    return _likelihood_result("Poisson CL-Test", forecast, catalog, qs, obs_ll, sims)


def window_years(window):
    """As floatCSEP scales gridded forecasts, time-dependent ones too: decimal years."""
    from csep.utils.time_utils import decimal_year

    return decimal_year(window[1]) - decimal_year(window[0])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--forecasts",
        required=True,
        help="folder with <MODEL>_01deg_rates.npy, the eight-year 0.1-degree forecasts",
    )
    parser.add_argument(
        "--annual-forecasts",
        required=True,
        help="folder with <MODEL>_<YEAR>_01deg_rates.npy, the annual experiment's",
    )
    args = parser.parse_args(argv)
    logging.disable(logging.WARNING)

    # A slot filled from another source has its 0.1-degree array named after the source
    # (models/sources.json, written by prepare.py)
    sources_file = os.path.join(HERE, "models", "sources.json")
    sources = json.load(open(sources_file)) if os.path.isfile(sources_file) else {}

    def array_path(model, window_str):
        """The forecast of a model for a time window, per year (see prepare.py)."""
        if model in TIME_VARYING and window_str != NATIVE_WINDOW:
            year = TIME_VARYING[model] or int(window_str[:4])
            return os.path.join(args.annual_forecasts, f"{model}_{year}_01deg_rates.npy")
        return os.path.join(args.forecasts, f"{sources.get(model, model)}_01deg_rates.npy")

    self_check()
    os.chdir(HERE)
    experiment = Experiment.from_yml(config_yml="config.yml")
    experiment.stage_models()
    experiment.set_tasks()
    magnitudes = numpy.asarray(experiment.magnitudes, dtype=float)
    tests = {t.func.__name__: t for t in experiment.tests}
    windows = [timewindow2str(w) for w in experiment.time_windows]
    paths = {(m, w): array_path(m, w) for m in MODELS for w in windows}
    missing = sorted({p for p in paths.values() if not os.path.isfile(p)})
    if missing:
        print("Missing 0.1-degree forecasts:\n  " + "\n  ".join(missing), file=sys.stderr)
        return 1

    t0 = time.time()
    print("Building the 0.1-degree grid (6.48 million cells)...", flush=True)
    region = native_region(magnitudes)
    arrays = {}  # by file, memory-mapped

    def rates(model, window_str):
        path = paths[(model, window_str)]
        if path not in arrays:
            arrays[path] = numpy.load(path, mmap_mode="r")
        return arrays[path]

    written = 0
    for window in experiment.time_windows:
        window_str = timewindow2str(window)
        try:
            catalog = experiment.catalog_repo.get_test_cat(window_str)
        except (FileNotFoundError, OSError):
            print(
                f"No test catalogue for {window_str}: run `floatcsep run config.yml` first.",
                file=sys.stderr,
            )
            return 1
        catalog.region = region
        catalog.filter_spatial(region=region, in_place=True)
        spatial_obs = catalog.spatial_counts()
        spatial_magnitude_obs = catalog.spatial_magnitude_counts()
        scale = window_years(window)
        out_dir = os.path.join(HERE, "imported", window_str)
        os.makedirs(out_dir, exist_ok=True)

        forecasts = {}
        for model in MODELS:
            forecast = GriddedForecast(
                data=numpy.asarray(rates(model, window_str)),
                region=region,
                magnitudes=magnitudes,
                name=f"{model}={GRID}",
                start_time=window[0],
                end_time=window[1],
            )
            forecasts[model] = forecast.scale(scale)

        for model in MODELS:
            forecast = forecasts[model]
            results = {}
            for fname, test in tests.items():
                kwargs = test.func_kwargs or {}
                if fname == "number_test":
                    results[test.name] = poisson_evaluations.number_test(forecast, catalog)
                elif fname == "magnitude_test":
                    results[test.name] = poisson_evaluations.magnitude_test(
                        forecast, catalog, **kwargs
                    )
                elif fname == "spatial_test":
                    results[test.name] = spatial_test(forecast, catalog, spatial_obs, **kwargs)
                elif fname == "conditional_likelihood_test":
                    results[test.name] = conditional_likelihood_test(
                        forecast, catalog, spatial_magnitude_obs, **kwargs
                    )
            if model != REF:
                results[T_TEST] = poisson_evaluations.paired_t_test(
                    forecast, forecasts[REF], catalog
                )
            for name, result in results.items():
                with open(os.path.join(out_dir, f"{name}_{model}={GRID}.json"), "w") as f:
                    json.dump(result.to_dict(), f, indent=4, cls=_NumpyEncoder)
                written += 1

        # Each model's rates at the target events (in the catalogue's order) and its
        # expected number of events, for the T-test pooled over several windows
        target = {}
        for model in MODELS:
            event_rates, total = forecasts[model].target_event_rates(catalog)
            target[model] = {
                "rates": numpy.asarray(event_rates).tolist(),
                "total": float(total),
            }
        with open(os.path.join(out_dir, "native_target_rates.json"), "w") as f:
            json.dump({"n_events": int(catalog.event_count), "models": target}, f)
        print(
            f"{window_str}: {catalog.event_count} events, {time.time() - t0:.0f} s", flush=True
        )

    print(f"Wrote {written} results on the native grid into imported/.")

    # The forecast arrays, for the dashboard's maps: they stay where they are
    declaration = {
        "grid": {
            "name": GRID,
            "lon0": -180.0,
            "lat0": -90.0,
            "dh": DH,
            "nx": 3600,
            "ny": 1800,
            "order": "lon-major",
        },
        "magnitudes": magnitudes.tolist(),
        "forecast_unit": 1,
        # One array for every window, or one per window for the time-dependent models
        "forecasts": {
            m: (
                {w: os.path.abspath(paths[(m, w)]) for w in windows}
                if m in TIME_VARYING
                else os.path.abspath(paths[(m, windows[0])])
            )
            for m in MODELS
        },
    }
    with open(os.path.join(HERE, "external_forecasts.json"), "w") as f:
        json.dump(declaration, f, indent=2)
    print("Wrote external_forecasts.json, for the dashboard's maps.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
