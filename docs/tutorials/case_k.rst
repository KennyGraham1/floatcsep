.. _case_k:

K — A Global Experiment on Quadtree Grids
=========================================

**Goal.** Test global forecasts of M7.45+ earthquakes on multi-resolution *quadtree* grids. Nine
forecasting models are each set up on eight quadtree grids (72 forecasts), evaluated year by year
and over the whole 2014–2021 testing period with Poisson consistency tests, and compared with the
GEAR1 benchmark on the same grid. The same tests are run on the models' native 0.1° grid, in
every time window, for comparison. A custom post-processing script adds the summary figures of the
experiment (score heatmaps across grids, information-gain rankings, yearly outcomes, a map of the
grids), and the Next.js dashboard shows the quadtree forecasts, the test scores, the grids and an
*About* page describing the experiment.

.. important::

   The input data of this tutorial are **not distributed with floatCSEP**: several of the forecasts
   are unpublished research output. ``prepare.py`` collects them from a local copy of the global
   quadtree experiment, and the copied files (``catalog.csv``, ``models/``, ``imported/``,
   ``about/``) and the ``results/`` folder are ignored by git.

.. admonition:: **TL; DR**

    In a terminal, navigate to ``floatcsep/tutorials/case_k`` and type:

    .. code-block:: console

        $ python prepare.py --source /path/to/globalExperiment
        $ floatcsep run config.yml

    Evaluating the 72 forecasts takes about 40 minutes on one core, mostly for the 10,000
    simulations of the M-, S- and CL-tests. For a quick run, prepare a single grid instead:

    .. code-block:: console

        $ python prepare.py --source /path/to/globalExperiment --grids N50L11

    To add the tests on the models' native 0.1° grid in every time window (about 10 minutes), point
    ``native_grid.py`` to the global experiment's 0.1° forecast arrays, eight-year and annual, and
    redraw the figures:

    .. code-block:: console

        $ python native_grid.py --forecasts /path/to/fullgrid_cache \
              --annual-forecasts /path/to/annual/native_cache
        $ floatcsep plot config.yml

    The forecasts, test scores and figures can then be explored in the **Experiment Dashboard**:

    .. code-block:: console

        $ floatcsep view config.yml --ui nextjs


.. currentmodule:: floatcsep

.. contents:: Contents
    :local:


Directory layout
----------------

After running ``prepare.py``, the experiment folder contains:

::

    case_k
        ├── about.md          # the dashboard's About page
        ├── about/            # its figures (copied by prepare.py)
        ├── catalog.csv       # gCMT catalog, Mw 5.65+, 0-70 km, 1976-2022 (written by prepare.py)
        ├── config.yml
        ├── custom_plots.py
        ├── imported/         # results on the native 0.1° grid, by time window
        ├── models/           # 72 forecasts (copied by prepare.py): <MODEL>=<GRID>.csv, or a
        │                     #   folder with one forecast per window for PPE, EEPASfull and SUP
        ├── models.yml        # rewritten by prepare.py
        ├── native_grid.py
        ├── prepare.py
        └── tests.yml


Preparing the inputs
--------------------

``prepare.py`` only reads the global experiment directory given with ``--source``:

- The forecasts ``gefe-quadtree_results_2023-03/regen/m745_models/<MODEL>=<GRID>.csv``: expected
  numbers of M7.45+ earthquakes per year in each quadtree cell and magnitude bin (7.45 to 8.95 in
  bins of 0.1), in floatCSEP's quadtree CSV format (a ``tile`` column with the cell quadkeys).
- The forecasts of the global experiment's annual experiment,
  ``gefe-quadtree_results_2023-03/regen/annual_models/<year>/<MODEL>=<GRID>.csv``, for PPE,
  EEPASfull and SUP.
- The gCMT catalog ``eepasModel/run/gcmt_M595_1976_2022.dat``, converted to the pyCSEP CSV format.

The models are:

==================  ==============================================================================
Model               Description
==================  ==============================================================================
``GEAR1``           Log-linear hybrid of smoothed seismicity and geodetic strain; the benchmark
``KJSS``            Kagan–Jackson smoothed seismicity
``SHIFT2F_GSRM``    Seismicity from the GSRM 2.1 strain rates
``TEAM``            Tectonic model: SMERF2 combined with a scaled SHIFT2F_GSRM
``WHEEL``           Log-linear hybrid of KJSS and TEAM
``EEPASfull``       Every Earthquake a Precursor According to Scale, mixed with PPE; reissued yearly
``PPE``             Proximity to Past Earthquakes; reissued yearly
``SUP``             Spatially uniform Poisson baseline
``GSSGSRM``         The SUP baseline modulated by the GSRM strain-rate alarm
==================  ==============================================================================

The first five are the published GEFE forecasts, time-independent like GSSGSRM. PPE and EEPASfull
are time-dependent: the global experiment's annual experiment reissues them every year from the
catalogue before that year. Tutorial K follows its two studies:

- The **whole period** uses the eight-year forecasts of every model, with PPE, EEPASfull and SUP
  fitted on the spliced ISC-GEM and gCMT catalogue before 2014.
- Each **year** uses the annual experiment's forecast for that year: PPE and EEPASfull reissued
  from the catalogue before it, and SUP's one baseline (its 2014 forecast), all three with the
  parameters fitted on the gCMT catalogue of 1994–2013. The six other models are the same.

The two fits differ, so for these three models the whole period and the years are not the same
forecasts: the T-test pooled over the years (``annual_pooled_ig.png``) is that of the annual
experiment, not that of the eight-year forecasts.

Every model is aggregated onto eight quadtree grids, named after how they were refined:

- ``N`` grids are refined from the earthquake catalog alone, ``SN`` grids from the catalog and
  the locations of GPS stations, so they are also denser where GPS networks are dense, even far
  from plate boundaries (for example in the eastern United States and Europe).
- The number (10, 25, 50 or 100) is the largest number of data points a cell may hold before it is
  split in four: a smaller number gives a finer grid.
- ``L11`` is the deepest zoom level: quadkeys of up to 11 characters, or cells of about 20 km at the
  equator.

==========  ========  ==========  ========
Grid        Cells     Grid        Cells
==========  ========  ==========  ========
N10L11      8,089     SN10L11     12,211
N25L11      3,502     SN25L11     5,308
N50L11      1,780     SN50L11     2,683
N100L11     922       SN100L11    1,432
==========  ========  ==========  ========

``--grids`` selects some of the grids (all eight by default); ``models.yml`` is rewritten to match.

``prepare.py`` also copies:

- The global experiment's results on the models' **native 0.1° grid** for the whole period, into
  ``imported/`` (skip them with ``--no-native``). ``native_grid.py`` recomputes them, and those
  of every year (see `The native 0.1° grid`_).
- The figures of ``about.md`` (how quadtree grids are built, the aggregation, the forecasts), into
  ``about/``. The other figures it shows are drawn by ``custom_plots.py``.


The native 0.1° grid
--------------------

The forecasts were made on a regular 0.1° grid before being aggregated onto the quadtree grids.
``native_grid.py`` tests them on that grid too, named ``FULL01``: 3,600 × 1,800 = 6.48 million
cells of about 11 km at the equator, with the same 16 magnitude bins. It reads the global
experiment's forecast arrays (expected events per year) where they are: the nine eight-year
forecasts (``<MODEL>_01deg_rates.npy``) for the whole period and, as on the quadtree grids, the
annual experiment's forecasts of PPE, EEPASfull and SUP (``<MODEL>_<YEAR>_01deg_rates.npy``) for
each year. It runs the tests of ``tests.yml`` with their settings, plus the paired T-test against
GEAR1 on the same grid, in every time window. The test catalogues are those of the floatCSEP run,
so ``floatcsep run`` comes first. The results go to ``imported/<time window>/``, where
``custom_plots.py`` picks them up, and ``floatcsep plot config.yml`` redraws the figures with them.

pyCSEP's S- and CL-tests clear and rescan the whole forecast in each of the 10,000 simulations
(104 million bins for the CL-test): on this grid, about five minutes per forecast for the S-test
and nearly two hours for the CL-test. ``native_grid.py`` draws the same random numbers and sums
the same terms over the sampled bins only. Its results are pyCSEP's (the simulated distributions
are identical), and agree with those of the global experiment to 1e-13. Because this relies on
pyCSEP's internals, the script first checks, on a small random forecast, that it still gives
exactly pyCSEP's numbers, and stops if it does not.

Aggregated exactly onto the quadtree grids, the 0.1° arrays reproduce the quadtree forecasts to a
relative 1e-12, and GSSGSRM's to 1e-5.

``native_grid.py`` also writes ``imported/<time window>/native_target_rates.json``, each model's
rates at the target events for the pooled T-test, and ``external_forecasts.json``: where the
forecast arrays are, one per window for the time-dependent models, so that the dashboard maps them
too. The dashboard reads the arrays where they are and sends each browser
the rate of every cell, so the forecasts can be explored down to the 0.1° cells.


Configuration
-------------

``config.yml``
^^^^^^^^^^^^^^

.. code-block:: yaml

   name: Global M7.45+ forecasts on quadtree grids

   time_config:
     exp_class: td
     # Eight annual windows, then the whole eight-year testing period.
     time_windows:
       - [2014-01-01T00:00:00, 2015-01-01T00:00:00]
       - [2015-01-01T00:00:00, 2016-01-01T00:00:00]
       # ... one window per year up to 2021
       - [2021-01-01T00:00:00, 2022-01-01T00:00:00]
       - [2014-01-01T00:00:00, 2022-01-01T00:00:00]

   region_config:
     mag_min: 7.45
     mag_max: 8.95
     mag_bin: 0.1
     depth_min: 0
     depth_max: 70

   catalog: catalog.csv
   models: models.yml
   test_config: tests.yml

   postprocess:
     plot_forecasts: False
     plot_custom: custom_plots.py:main

**Notes**

- ``exp_class: td`` makes it a time-dependent experiment: in every window the forecasts are issued
  from the data before it, PPE and EEPASfull reissued each year. With explicit ``time_windows``, the
  class does not change the windows; floatCSEP also writes the input catalogs that time-dependent
  models are given (not used here, as their forecasts are files).
- ``time_windows`` lists the testing windows explicitly: eight one-year windows and the whole
  eight-year period. The forecasts are rates per year (``forecast_unit: 1`` in ``models.yml``), and
  floatCSEP scales them to the length of each window. The time-dependent models have one forecast
  per window, which floatCSEP also scales by the window's length in years.
- ``region_config`` has no ``region``. Each forecast is then tested on its own region, the quadtree
  grid read from its file, and the test catalog is filtered to the cells of that grid.
- ``plot_forecasts: False`` skips the static maps of the 72 forecasts in every window; they are
  easier to explore in the dashboard. ``plot_custom`` runs ``main(experiment)`` from
  ``custom_plots.py`` once the evaluations are done (see :ref:`postprocess`).

``models.yml``
^^^^^^^^^^^^^^

Written by ``prepare.py``, with one entry per model and grid:

.. code-block:: yaml

   - GEAR1=N10L11:
       path: models/GEAR1=N10L11.csv
       forecast_unit: 1
       description: "Log-linear hybrid of smoothed seismicity and geodetic strain; ..."
   - EEPASfull=N10L11:
       path: models/EEPASfull=N10L11
       class: td
       forecast_type: gridded
       description: "Every Earthquake a Precursor According to Scale, mixed with PPE. ..."
   # ...

A time-dependent model (``class: td``) is a folder whose ``forecasts/`` hold one file per time
window, ``<MODEL>=<GRID>_<start>_<end>.csv``; floatCSEP finds them there and runs nothing.
``forecast_type: gridded`` tells it that they are gridded forecasts, not catalogs. The custom
script and the dashboard read the ``<MODEL>=<GRID>`` names to group the forecasts by model and by
grid; the dashboard shows the descriptions in its table of models.

``tests.yml``
^^^^^^^^^^^^^

.. code-block:: yaml

   - Poisson N-test:
       func: poisson_evaluations.number_test
       plot_func: plot_consistency_test
       plot_args:
         title: Poisson N-test
         xlabel: Number of events

   - Poisson S-test:
       func: poisson_evaluations.spatial_test
       func_kwargs:
         num_simulations: 10000
         seed: 23
       plot_func: plot_consistency_test
       plot_args:
         title: Poisson S-test
         xlabel: Log-likelihood
       plot_kwargs:
         one_sided_lower: True

   # The M-test and CL-test are set up like the S-test.

**Notes**

- The M-, S- and CL-tests simulate 10,000 catalogs with a fixed ``seed``, so their results are
  reproducible.
- ``one_sided_lower`` draws the likelihood tests as one-sided tests in the consistency plots.
- There is no paired T-test in this file. A floatCSEP test has a single ``ref_model``, whereas here
  each model is compared with GEAR1 *on its own grid*: the custom script runs these T-tests.


Custom post-processing
----------------------

``custom_plots.py`` receives the :class:`~floatcsep.experiment.Experiment` once the evaluations are
done, and:

1. Runs the paired T-test of every model against GEAR1 on the same grid, in every time window, with
   :func:`csep.core.poisson_evaluations.paired_t_test`. Each result is stored like floatCSEP's own,
   as ``results/<window>/evaluations/Paired T-test_<MODEL>=<GRID>.json``.
2. Stores the results on the native grid from ``imported/`` the same way, in their windows.
3. Draws the summary figures of the global experiment into ``results/figures/``, with the native
   grid as a ninth column of the whole-period figures, and yearly figures for it:

   ==============================  ==============================================================
   Figure                          Content
   ==============================  ==============================================================
   ``{N,M,S,CL}_heatmap.png``      Test scores over the whole period, models × grids; rejected
                                   cells are hatched and outlined
   ``{N,M,S,CL}_facets.png``       Simulated 95% intervals and observed statistics, one panel per
                                   grid
   ``T_ranked.png``                Information gain against GEAR1, per model and grid; models
                                   ranked by their mean over the quadtree grids
   ``annual_consistency.png``      Test outcomes by year, on grid N50L11
   ``annual_ig_heatmap.png``       Information gain against GEAR1 by year, on grid N50L11
   ``annual_counts.png``           Forecast and observed numbers of events by year
   ``annual_pooled_ig.png``        T-test pooling the events of the eight annual windows
   ``annual_*_native.png``         The yearly test outcomes, information gains and pooled T-test on
                                   the native grid (after ``native_grid.py``)
   ``quadtree_grids.png``          Maps of the quadtree grids and of the native 0.1° grid
                                   (``cartopy``)
   ``grid_levels.png``             The grids compared: cells per zoom level, cells against N
   ``quadtree_japan.png``          Three grids and the native 0.1° lattice around Japan,
                                   and how quadkeys nest
                                   (``cartopy``)
   ==============================  ==============================================================


What happens under the hood
---------------------------

1. floatCSEP reads the nine time windows and the 72 models. Each forecast file has a ``tile``
   column, so it is read as a quadtree forecast on a :class:`csep.core.regions.QuadtreeGrid2D`.
2. In each window, the yearly rates are scaled to the window length: by 1 for the annual windows
   and by 8 for the whole period. The time-dependent models use their forecast for that window.
3. The test catalog of each window is filtered to the magnitude range and to each forecast's
   grid, and the N-, M-, S- and CL-tests run: 72 forecasts × 9 windows × 4 tests = 2,592
   evaluations. floatCSEP keeps the events of M ≥ 7.45 and below ``mag_max`` (8.95), although the
   last magnitude bin is open-ended, so an M ≥ 8.95 event would not be tested; none occurred, the
   largest target is M 8.27. It does not filter by depth: ``prepare.py`` keeps the events at
   0–70 km when it writes ``catalog.csv``.
4. The consistency plots of each test and window are drawn, then ``custom_plots.main`` runs.


Outputs
-------

You should find:

- Test results (JSON) in ``results/{time_window}/evaluations``, including the same-grid T-tests and
  the results on the native grid (``<test>_<MODEL>=FULL01.json``)
- Consistency plots in ``results/{time_window}/figures``
- The summary figures in ``results/figures``
- A Markdown report summarizing the experiment in ``results/report.md``


Exploring the results in the dashboard
--------------------------------------

The Next.js dashboard (``floatcsep view config.yml --ui nextjs``, see :ref:`running`) recognizes the
quadtree grids and the ``<MODEL>=<GRID>`` names. Global maps are centred on the Pacific.

- **Overview** maps the forecast grids, with a selector for the eight quadtree grids; each cell is
  shaded by its zoom level. The native grid is listed below the map, with links to its forecasts
  and results.
- **About** shows ``about.md``: how the quadtree grids are built, the aggregation of the 0.1°
  forecasts onto them, the models and the tests, with the global experiment's figures.
- **Forecasts** selects a model and a grid, the native 0.1° grid included once ``native_grid.py``
  has run. The map shows the expected number of events per cell or, better suited to cells of very
  different sizes, per 10⁴ km² (the *rate density*), with the observed events of the time window on
  top.
- **Results**, *Charts* view: heatmaps of the test scores, as models × grids for a time window
  (with the native 0.1° grid for the whole period) or models × time windows for a grid, including
  the same-grid T-tests. Selecting a cell shows the intervals of that test for every model.
- **Results**, *Figures* view: the consistency plots of every test and window, and the summary
  figures of ``results/figures`` under *Experiment figures*.

Every chart has a table view, and every table can be downloaded as CSV.


pyCSEP under the hood
---------------------

    **Classes and functions used in this tutorial**

    - Catalog: :py:class:`csep.core.catalogs.CSEPCatalog`
    - Region: :py:class:`csep.core.regions.QuadtreeGrid2D`
    - Forecast class: :py:class:`csep.core.forecasts.GriddedForecast`

        - :meth:`floatcsep.utils.file_io.GriddedForecastParsers.quadtree`

    - Test functions:

        - :py:func:`csep.core.poisson_evaluations.number_test`
        - :py:func:`csep.core.poisson_evaluations.magnitude_test`
        - :py:func:`csep.core.poisson_evaluations.spatial_test`
        - :py:func:`csep.core.poisson_evaluations.conditional_likelihood_test`
        - :py:func:`csep.core.poisson_evaluations.paired_t_test`

    - Result plotting functions:

        - :py:func:`csep.utils.plots.plot_consistency_test`


    **Where to learn pyCSEP further:**

    - :doc:`pycsep:concepts/regions`
    - :doc:`pycsep:concepts/forecasts`
    - :doc:`pycsep:concepts/evaluations`
