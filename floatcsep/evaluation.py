import datetime
import logging
import os
from typing import Dict, Callable, Union, Sequence, List, Any

import numpy
from csep.core.catalogs import CSEPCatalog
from csep.core.forecasts import GriddedForecast
from matplotlib import pyplot

from floatcsep.model import Model
from floatcsep.infrastructure.registries import ExperimentRegistry
from floatcsep.utils.helpers import parse_csep_func

log = logging.getLogger("floatLogger")


# Tolerance, in tiles, for points computed to lie on a tile edge
_TILE_EDGE = 1e-9


def _quadtree_tiles(quadkeys) -> dict:
    """
    The cells of a quadtree grid by zoom level: their Web Mercator tiles, coded as
    ``x * 2**level + y`` and sorted, and the index of each cell in the grid.
    """
    levels = {}
    for index, key in enumerate(quadkeys):
        key = str(key)
        x = y = 0
        for digit in key:  # each digit picks a quadrant: bit 0 is x, bit 1 is y
            d = int(digit)
            x, y = 2 * x + (d & 1), 2 * y + (d >> 1)
        codes, cells = levels.setdefault(len(key), ([], []))
        codes.append(x * 2 ** len(key) + y)
        cells.append(index)
    tiles = {}
    for level, (codes, cells) in levels.items():
        order = numpy.argsort(codes)
        tiles[level] = (
            numpy.asarray(codes, dtype=numpy.int64)[order],
            numpy.asarray(cells)[order],
        )
    return tiles


def inside_quadtree(region, lons, lats) -> numpy.ndarray:
    """
    Whether each point lies in a cell of a quadtree grid, by the test of pyCSEP's
    ``QuadtreeGrid2D`` (``west <= lon < east`` and ``south <= lat < north``).

    Rather than testing every cell, the candidate cells of a point are its Web Mercator
    tiles at each zoom level of the grid (both tiles, where the point is on an edge), and
    only those are tested. The result is the same, in O(points x levels).
    """
    lons = numpy.asarray(lons, dtype=float)
    lats = numpy.asarray(lats, dtype=float)
    bounds = numpy.asarray(region.bounds, dtype=float)
    inside = numpy.zeros(lons.shape, dtype=bool)
    with numpy.errstate(all="ignore"):
        x_unit = (lons + 180.0) / 360.0
        sin = numpy.sin(numpy.radians(lats))
        y_unit = 0.5 - numpy.log((1.0 + sin) / (1.0 - sin)) / (4.0 * numpy.pi)
    for level, (codes, cells) in _quadtree_tiles(region.quadkeys).items():
        n = 2**level
        for dx in (-_TILE_EDGE, _TILE_EDGE):
            for dy in (-_TILE_EDGE, _TILE_EDGE):
                with numpy.errstate(invalid="ignore"):
                    x = numpy.floor(x_unit * n + dx)
                    y = numpy.floor(y_unit * n + dy)
                    valid = (x >= 0) & (x < n) & (y >= 0) & (y < n)
                xi = numpy.where(valid, x, 0).astype(numpy.int64)
                yi = numpy.where(valid, y, 0).astype(numpy.int64)
                code = numpy.where(valid, xi * n + yi, -1)
                pos = numpy.minimum(numpy.searchsorted(codes, code), codes.size - 1)
                cell = cells[pos]
                west, south, east, north = bounds[cell].T
                inside |= (
                    valid
                    & (codes[pos] == code)
                    & (west <= lons)
                    & (lons < east)
                    & (south <= lats)
                    & (lats < north)
                )
    return inside


def filter_to_region(catalog: CSEPCatalog, region) -> CSEPCatalog:
    """
    Keeps only the events of a catalog that fall inside the cells of a region.

    Cartesian grids provide a mask (``get_masked``); quadtree grids do not, so their
    events are kept when they lie within the bounds of any of the grid's cells.
    """
    if hasattr(region, "get_masked"):
        return catalog.filter_spatial(region=region, in_place=True)
    catalog.region = region
    if catalog.event_count == 0:
        return catalog
    lons, lats = catalog.get_longitudes(), catalog.get_latitudes()
    if hasattr(region, "quadkeys"):
        inside = inside_quadtree(region, lons, lats)
    else:
        west, south, east, north = numpy.asarray(region.bounds).T
        inside = numpy.array(
            [
                numpy.any((west <= lon) & (lon < east) & (south <= lat) & (lat < north))
                for lon, lat in zip(lons, lats)
            ],
            dtype=bool,
        )
    catalog.catalog = catalog.catalog[inside]
    return catalog


class Evaluation:
    """
    Class representing a Scoring Test, which wraps the evaluation function, its arguments,
    parameters and hyperparameters.

    Args:
        name (str): Name of the Test.
        func (str, ~typing.Callable): Test function/callable.
        func_kwargs (dict): Keyword arguments of the test function.
        ref_model (str): String of the reference model, if any.
        plot_func (str, ~typing.Callable): Test's plotting function.
        plot_args (list,dict): Positional arguments of the plotting function.
        plot_kwargs (list,dict): Keyword arguments of the plotting function.
        markdown (str): The caption to be placed beneath the result figure.
    """

    _TYPES = {
        "number_test": "consistency",
        "spatial_test": "consistency",
        "magnitude_test": "consistency",
        "likelihood_test": "consistency",
        "conditional_likelihood_test": "consistency",
        "negative_binomial_number_test": "consistency",
        "binary_spatial_test": "consistency",
        "binomial_spatial_test": "consistency",
        "brier_score": "consistency",
        "binary_conditional_likelihood_test": "consistency",
        "paired_t_test": "comparative",
        "paired_ttest_point_process": "comparative",
        "w_test": "comparative",
        "binary_paired_t_test": "comparative",
        "vector_poisson_t_w_test": "batch",
        "sequential_likelihood": "sequential",
        "sequential_information_gain": "sequential_comparative",
    }


    _PLOTS = {
        "csep.plots.plot_consistency_test": "aggregate",
        "csep.plots.plot_comparison_test": "aggregate",
        "csep.plots.plot_magnitude_test": "per_model",
        "csep.plots.plot_test_distribution": "per_model",
        "csep.plots.plot_calibration_test": "per_model",
        "csep.plots.plot_concentration_ROC_diagram": "per_model",
        "csep.plots.plot_ROC_diagram": "per_model",
        "csep.plots.plot_Molchan_diagram": "per_model",
        "floatcsep.utils.helpers.plot_matrix_comparative_test": "aggregate",
        "floatcsep.utils.helpers.plot_sequential_likelihood": "sequential",
    }

    def __init__(
        self,
        name: str,
        func: Union[str, Callable],
        func_kwargs: Dict = None,
        ref_model: (str, Model) = None,
        plot_func: Callable = None,
        plot_args: Sequence = None,
        plot_kwargs: Dict = None,
        markdown: str = "",
    ) -> None:

        self.name = name

        self.func = parse_csep_func(func)
        self.func_kwargs = func_kwargs or {}
        self.ref_model = ref_model

        self.plot_func = None
        self.plot_args = None
        self.plot_kwargs = None
        self.plot_modes = []
        self.parse_plots(plot_func, plot_args, plot_kwargs)

        self.markdown = markdown
        self.type = Evaluation._TYPES.get(self.func.__name__)

        self.results_repo = None
        self.catalog_repo = None
        self.strict_region = True  # If True, raise error when forecast region differs

    @property
    def type(self):
        """
        Returns the type of the test, mapped from the class attribute Evaluation._TYPES.
        """
        return self._type

    @type.setter
    def type(self, type_list: Union[str, Sequence[str]]):
        if isinstance(type_list, Sequence):
            if ("Comparative" in type_list) and (self.ref_model is None):
                raise TypeError(
                    "A comparative-type test should have a" " reference model assigned"
                )

        self._type = type_list

    def parse_plots(
        self,
        plot_func: Any,
        plot_args: Any,
        plot_kwargs: Any,
    ) -> None:
        """
        It parses the plot function(s) and its(their) arguments from the test configuration
        file. The plot function can belong to :mod:`csep.utils.plots` or a custom function.
        Each plotting function is parsed by using the function
        :func:`~floatcsep.utils.helpers.parse_csep_function`, and assigned to its respective
        `args` and `kwargs`

        Args:
            plot_func: The name of the plotting function
            plot_args: The arguments of the plotting function
            plot_kwargs: The keyword arguments of the plotting function


        """
        if isinstance(plot_func, str):
            try:
                self.plot_func = [parse_csep_func(plot_func)]
            except AttributeError:
                self.plot_func = [None]
            self.plot_args = [plot_args] if plot_args else [{}]
            self.plot_kwargs = [plot_kwargs] if plot_kwargs else [{}]

        elif isinstance(plot_func, (list, dict)):
            if isinstance(plot_func, dict):
                plot_func = [{i: j} for i, j in plot_func.items()]

            if plot_args is not None or plot_kwargs is not None:
                raise ValueError(
                    "If multiple plot functions are passed,"
                    "each func should be a dictionary with "
                    "plot_args and plot_kwargs passed as "
                    "dictionaries beneath each func."
                )

            func_names = [list(i.keys())[0] for i in plot_func]
            self.plot_func = [parse_csep_func(func) for func in func_names]
            self.plot_args = [i[j].get("plot_args", {}) for i, j in zip(plot_func, func_names)]
            self.plot_kwargs = [
                i[j].get("plot_kwargs", {}) for i, j in zip(plot_func, func_names)
            ]
        else:
            return
        for func_obj in self.plot_func:
            if func_obj is not None:
                func_name = f"{func_obj.__module__}.{func_obj.__name__}"
                mode = self._PLOTS[func_name]

                if mode is None:
                    if self.type in ["sequential", "sequential_comparative", "batch"]:
                        mode = "sequential"
                    else:
                        mode = "aggregate"

                self.plot_modes.append(mode)

    def prepare_args(
        self,
        timewindow: Union[str, list],
        model: Union[Model, Sequence[Model]],
        ref_model: Union[Model, Sequence] = None,
        region=None,
    ) -> tuple:
        """
        Prepares the positional argument for the Evaluation function.

        Args:
            timewindow (str, list): Time window string (or list of str)
             formatted from :meth:`floatcsep.utils.timewindow2str`
            model (:class:`floatcsep:model.Model`): Model to be evaluated
            ref_model (:class:`floatcsep:model.Model`, list): Reference model (or
             models) reference for the evaluation.
            region (:class:`csep:core.regions.CartesianGrid2D`): Experiment region

        Returns:
            A tuple of the positional arguments required by the evaluation
            function :meth:`Evaluation.func`.
        """
        # Subtasks
        # ========
        # Get forecast from model
        # Read Catalog
        # Share forecast region with catalog
        # Check if ref_model is None, Model or List[Model]
        # Prepare argument tuple

        forecast = model.get_forecast(timewindow, region)
        catalog = self.get_catalog(timewindow, forecast, experiment_region=region)

        if isinstance(ref_model, Model):
            # Args: (Fc, RFc, Cat)
            ref_forecast = ref_model.get_forecast(timewindow, region)
            test_args = (forecast, ref_forecast, catalog)
        elif isinstance(ref_model, list):
            # Args: (Fc, [RFc], Cat)
            ref_forecasts = [i.get_forecast(timewindow, region) for i in ref_model]
            test_args = (forecast, ref_forecasts, catalog)
        else:
            # Args: (Fc, Cat)
            test_args = (forecast, catalog)

        return test_args

    def get_catalog(
        self,
        timewindow: Union[str, Sequence[str]],
        forecast: Union[GriddedForecast, Sequence[GriddedForecast]],
        experiment_region=None,
    ) -> Union[CSEPCatalog, List[CSEPCatalog]]:
        """
        Reads the catalog(s) from the given path(s). References the catalog region to the
        forecast region and filters events to ensure they fall within the forecast region.

        Args:
            timewindow (str): Time window of the testing catalog
            forecast (:class:`~csep.core.forecasts.GriddedForecast`): Forecast
             object, onto which the catalog will be confronted for testing.
            experiment_region: The experiment's configured region for comparison

        Returns:
        """

        # Tests that require spatial binning and need strict region matching
        _SPATIAL_TESTS = {
            "spatial_test",
            "binary_spatial_test", 
            "binomial_spatial_test",
            "likelihood_test",
            "conditional_likelihood_test",
        }
        is_spatial_test = self.func.__name__ in _SPATIAL_TESTS

        def _check_region_mismatch(fc_region, exp_region, timewindow_str):
            """Check if forecast region differs from experiment region."""
            if fc_region is None or exp_region is None:
                return
            fc_bbox = fc_region.get_bbox()
            exp_bbox = exp_region.get_bbox()
            if fc_bbox != exp_bbox:
                msg = (
                    f"Forecast region {fc_bbox} differs from experiment region {exp_bbox} "
                    f"for time window {timewindow_str}. Filtering catalog to forecast region."
                )
                # Only raise error for spatial tests when strict_region is True
                if self.strict_region and is_spatial_test:
                    raise ValueError(
                        f"strict_region=True: {msg} "
                        "Set strict_region: false in region_config to allow auto-filtering."
                    )
                else:
                    log.warning(msg)

        if isinstance(timewindow, str):
            # eval_cat = CSEPCatalog.load_json(catalog_path)
            eval_cat = self.catalog_repo.get_test_cat(timewindow)
            eval_cat.region = getattr(forecast, "region")
            # Check for region mismatch and warn/error
            _check_region_mismatch(forecast.region, experiment_region, timewindow)
            # Filter catalog to forecast region to prevent spatial test failures
            if forecast.region is not None:
                filter_to_region(eval_cat, forecast.region)

        else:
            eval_cat = [self.catalog_repo.get_test_cat(i) for i in timewindow]
            if (len(forecast) != len(eval_cat)) or (not isinstance(forecast, Sequence)):
                raise IndexError("Amount of passed catalogs and forecasts must " "be the same")
            for i, (cat, fc) in enumerate(zip(eval_cat, forecast)):
                cat.region = getattr(fc, "region", None)
                # Check for region mismatch and warn/error
                tw_str = timewindow[i] if isinstance(timewindow, list) else str(i)
                _check_region_mismatch(fc.region, experiment_region, tw_str)
                # Filter catalog to forecast region
                if fc.region is not None:
                    filter_to_region(cat, fc.region)

        return eval_cat

    def compute(
        self,
        timewindow: Union[str, list],
        model: Model,
        ref_model: Union[Model, Sequence[Model]] = None,
        region=None,
    ) -> None:
        """
        Runs the test, structuring the arguments according to the
        test-typology/function-signature

        Args:
            timewindow (list[~datetime.datetime, ~datetime.datetime]): A pair of datetime
             objects representing the testing time span
            catalog (str):  Path to the filtered catalog
            model (Model, list[Model]): Model(s) to be evaluated
            ref_model: Model to be used as reference
            region: region to filter a catalog forecast.

        Returns:
        """
        test_args = self.prepare_args(
            timewindow, model=model, ref_model=ref_model, region=region
        )

        evaluation_result = self.func(*test_args, **self.func_kwargs)

        if self.type in ["sequential", "sequential_comparative"]:
            self.results_repo.write_result(evaluation_result, self, model, timewindow[-1])
        else:
            self.results_repo.write_result(evaluation_result, self, model, timewindow)

    def read_results(
        self, window: Union[str, Sequence[datetime.datetime]], models: Union[Model, List[Model]]
    ) -> List:
        """
        Reads an Evaluation result for a given time window and returns a list of the results for
        all tested models.
        """

        test_results = self.results_repo.load_results(self, window, models)

        return test_results

    def as_dict(self) -> dict:
        """
        Represents an Evaluation instance as a dictionary, which can be serialized and then
        parsed
        """
        out = {}
        included = ["model", "ref_model", "func_kwargs"]
        for k, v in self.__dict__.items():
            if k in included and v:
                out[k] = v
        func_str = f"{self.func.__module__}.{self.func.__name__}"

        plot_func_str = []
        for i, j, k in zip(self.plot_func, self.plot_args, self.plot_kwargs):
            pfunc = {f"{i.__module__}.{i.__name__}": {"plot_args": j, "plot_kwargs": k}}
            plot_func_str.append(pfunc)

        return {self.name: {**out, "func": func_str, "plot_func": plot_func_str}}

    def __str__(self):
        return (
            f"name: {self.name}\n"
            f"function: {self.func.__name__}\n"
            f"reference model: {self.ref_model}\n"
            f"kwargs: {self.func_kwargs}\n"
        )

    @classmethod
    def from_dict(cls, record):
        """Parses a dictionary and re-instantiate an Evaluation object."""
        if len(record) != 1:
            raise IndexError("A single test has not been passed")
        name = next(iter(record))
        return cls(name=name, **record[name])
