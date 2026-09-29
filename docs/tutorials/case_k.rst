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
    ``native_grid.py`` to the global experiment's 0.1° forecast arrays and redraw the figures:

    .. code-block:: console

        $ python native_grid.py --forecasts /path/to/fullgrid_cache
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
        ├── catalog.csv       # gCMT catalog, M5.95+, 1976-2022 (written by prepare.py)
        ├── config.yml
        ├── custom_plots.py
        ├── imported/         # results on the native 0.1° grid, by time window
        ├── models/           # 72 forecasts, <MODEL>=<GRID>.csv (copied by prepare.py)
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
- The gCMT catalog ``eepasModel/run/gcmt_M595_1976_2022.dat``, converted to the pyCSEP CSV format.

The models are:

==================  ==============================================================================
Model               Description
==================  ==============================================================================
``GEAR1``           Global Earthquake Activity Rate model (published GEFE forecast; the benchmark)
``KJSS``            Kagan–Jackson smoothed seismicity (published GEFE forecast)
``SHIFT2F_GSRM``    SHIFT model on the GSRM strain rates (published GEFE forecast)
``TEAM``            TEAM ensemble (published GEFE forecast)
``WHEEL``           WHEEL ensemble (published GEFE forecast)
``EEPASfull``       EEPAS mixed with PPE, (1 − μ) EEPAS + μ PPE
``PPE``             Proximity to Past Earthquakes
``SUP``             Spatially uniform baseline
``GSSGSRM``         Hybrid of SUP and the GSRM strain rates
==================  ==============================================================================

Every model is aggregated onto eight quadtree grids, named after how they were refined:

- ``N`` grids are refined from the earthquake catalog alone, ``SN`` grids from the catalog and
  geodetic strain-rate data, so they are denser along plate boundaries.
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
- The figures of ``about.md`` (how quadtree grids are built, the grids, the aggregation, the
  forecasts), into ``about/``.


The native 0.1° grid
--------------------

The forecasts were made on a regular 0.1° grid before being aggregated onto the quadtree grids.
``native_grid.py`` tests them on that grid too, named ``FULL01``: 3,600 × 1,800 = 6.48 million
cells of about 11 km at the equator, with the same 16 magnitude bins. It reads the global
experiment's nine forecast arrays (``<MODEL>_01deg_rates.npy``, expected events per year) where
they are, and runs the tests of ``tests.yml`` with their settings, plus the paired T-test against
GEAR1 on the same grid, in every time window. The test catalogues are those of the floatCSEP run,
so ``floatcsep run`` comes first. The results go to ``imported/<time window>/``, where
``custom_plots.py`` picks them up, and ``floatcsep plot config.yml`` redraws the figures with them.

pyCSEP's S- and CL-tests clear and rescan the whole forecast in each of the 10,000 simulations
(104 million bins for the CL-test), which takes hours per forecast on this grid. ``native_grid.py``
draws the same random numbers and sums the same terms over the sampled bins only. Its results
agree with pyCSEP's within rounding, and with those of the global experiment.


Configuration
-------------

``config.yml``
^^^^^^^^^^^^^^

.. code-block:: yaml

   name: Global M7.45+ forecasts on quadtree grids

   time_config:
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

- ``time_windows`` lists the testing windows explicitly: eight one-year windows and the whole
  eight-year period. The forecasts are rates per year (``forecast_unit: 1`` in ``models.yml``), and
  floatCSEP scales them to the length of each window.
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
       description: Global Earthquake Activity Rate model (published GEFE forecast, benchmark)
   - KJSS=N10L11:
       path: models/KJSS=N10L11.csv
       forecast_unit: 1
       description: Kagan-Jackson smoothed seismicity (published GEFE forecast)
   # ...

The custom script and the dashboard read the ``<MODEL>=<GRID>`` names to group the forecasts by
model and by grid.

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
   ``T_ranked.png``                Information gain against GEAR1, per model and grid
   ``annual_consistency.png``      Test outcomes by year, on grid N50L11
   ``annual_ig_heatmap.png``       Information gain against GEAR1 by year, on grid N50L11
   ``annual_counts.png``           Forecast and observed numbers of events by year
   ``annual_pooled_ig.png``        T-test pooling the events of the eight annual windows
   ``annual_*_native.png``         The yearly test outcomes and information gains on the native
                                   grid (after ``native_grid.py``)
   ``quadtree_grids.png``          Map of the grids (drawn only if ``cartopy`` is installed)
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
   and by 8 for the whole period.
3. The test catalog of each window (M ≥ 7.45, depths of 0–70 km) is filtered to each forecast's
   grid, and the N-, M-, S- and CL-tests run: 72 forecasts × 9 windows × 4 tests = 2,592
   evaluations.
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

- **Overview** maps the forecast grids, with a selector for the eight grids; each cell is shaded by
  its zoom level.
- **About** shows ``about.md``: how the quadtree grids are built, the aggregation of the 0.1°
  forecasts onto them, the models and the tests, with the global experiment's figures.
- **Forecasts** selects a model and a grid. The map shows the expected number of events per cell or,
  better suited to cells of very different sizes, per 10⁴ km² (the *rate density*), with the
  observed events of the time window on top.
- **Results**, *Charts* view: heatmaps of the test scores, as models × grids for a time window
  (with the native 0.1° grid for the whole period) or models × time windows for a grid, including
  the same-grid T-tests. Selecting a cell shows the intervals of that test for every model.
- **Results**, *Figures* view: the consistency plots of every test and window, and the summary
  figures of ``results/figures`` under *Experiment figures*.


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
