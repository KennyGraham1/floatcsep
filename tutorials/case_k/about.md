# Global M7.45+ forecasts on multi-resolution quadtree grids

This experiment tests nine global forecasts of large earthquakes, M ≥ 7.45, against
the gCMT catalogue over 2014–2021. Every forecast is aggregated onto eight
data-adaptive quadtree grids and tested on each of them, and on the models' native
0.1° grid, with the CSEP consistency and comparison tests. It follows the RISE/CSEP
Global Earthquake Forecasting Experiment (GEFE), which tests M ≥ 5.95 forecasts on the
same kind of grids, and extends it to large events and to newly fitted models.

The forecasts, the catalogue and the figures on this page are copied from the global
experiment by `prepare.py` (Tutorial K of the floatCSEP documentation).

## Quadtree grids

A quadtree grid covers the globe with Web-Mercator tiles of different sizes. Starting
from the whole world, a tile is split into four whenever it holds more than N data
points, down to a maximum zoom level L. Each tile is named by its quadkey: every digit
selects a quadrant of the parent tile (0, 1, 2, 3 = NW, NE, SW, SE), so the length of
the key is the tile's zoom level and a child's key extends its parent's.

![Building a quadtree, step by step, on synthetic points with N = 8: the root tile is split, then every child holding more than N points, until no cell holds more than N points.](about/fig_quadtree_build.png)

The names of the grids encode the refinement rule:

- **N** grids are refined from the earthquake catalogue alone; **SN** grids from the
  catalogue together with the geodetic strain-rate points of the Global Strain Rate
  Map (GSRM), which makes them denser along plate boundaries.
- The number (10, 25, 50 or 100) is the largest number of points a cell may hold before
  it is split: a smaller number gives a finer grid.
- **L11** is the maximum zoom level: quadkeys of up to 11 characters, or cells of about
  20 km at the equator.

| Grid    | Cells | Grid     | Cells  |
| ------- | ----: | -------- | -----: |
| N10L11  | 8,089 | SN10L11  | 12,211 |
| N25L11  | 3,502 | SN25L11  | 5,308  |
| N50L11  | 1,780 | SN50L11  | 2,683  |
| N100L11 | 922   | SN100L11 | 1,432  |

![The eight grids compared: (a) the number of cells at each zoom level, with the width of the cells at the equator; (b) the number of cells against N. A smaller N, or adding the strain-rate points, gives more and smaller cells.](results/figures/grid_levels.png)

![The evaluation grids on Pacific-centred maps: (a–h) the eight quadtree grids, (i) the models' native 0.1° grid of 6.48 million cells, drawn at 2° spacing, with the true cells over central Japan in the inset.](about/quadtree_grids.png)

![Grids around Japan. Three quadtree grids, with their cells shaded by zoom level: N10L11 is finer than N50L11, and SN10L11 adds cells where the strain-rate points are dense. In N50L11, the cell holding the 2011 Tohoku epicentre (L9) is outlined with two of the tiles it was split from (L7, L5): each digit of a quadkey selects a quadrant, so a child's key extends its parent's. Last, the models' native 0.1° grid, a regular lattice finer than any quadtree cell.](results/figures/quadtree_japan.png)

As Web-Mercator grids, the tiles end at latitude ±85.05°: the forecasts and the tests
are defined on that domain, and all the target earthquakes fall inside every grid.

## From 0.1° forecasts to quadtree cells

All nine forecasts are given on 0.1° longitude–latitude grids. Source cells and
quadtree tiles are both rectangles in longitude and latitude, so the weight of a source
cell in a tile is the fraction of its longitude range inside the tile times the fraction
of its latitude range, measured in sin(latitude), which is exact on the sphere. The rate
of a tile is the weighted sum of the source rates, with no resampling.

![Exact area-weighted aggregation: (a) the weight of a source cell in a tile; (b) the weights on a real tile of N50L11; (c) the check against the distributed GEFE forecast for that tile.](about/aggregation.png)

## The native 0.1° grid

Every forecast is also tested on the grid it was made on, without any aggregation: the
regular 0.1° lattice of 3,600 × 1,800 = 6.48 million cells (about 11 km at the
equator), with the same 16 magnitude bins, in every time window. In the results this
grid is named **FULL01** (0.1°): it shows how much the verdicts on the quadtree grids
depend on the size of their cells.

The tests and their settings are the same as on the quadtree grids. pyCSEP's S- and
CL-tests, however, clear and rescan the whole forecast in each of the 10,000
simulations, 104 million bins for the CL-test, which takes hours per forecast on this
grid. `native_grid.py` draws the same random numbers and sums the same terms over the
sampled bins only, which gives the same results as pyCSEP within rounding, in seconds.

## Models

| Group            | Model        | Method                                                                   |
| ---------------- | ------------ | ------------------------------------------------------------------------ |
| GEFE (published) | GEAR1        | Log-linear hybrid of smoothed seismicity and geodetic strain; benchmark   |
| GEFE (published) | KJSS         | Kagan–Jackson smoothed seismicity                                        |
| GEFE (published) | SHIFT2F_GSRM | Seismicity from the GSRM 2.1 strain rates                                |
| GEFE (published) | TEAM         | Tectonic model: SMERF2 combined with a scaled SHIFT2F_GSRM               |
| GEFE (published) | WHEEL        | Log-linear hybrid of KJSS and TEAM                                       |
| EEPAS family     | SUP          | Spatially uniform Poisson baseline                                       |
| EEPAS family     | PPE          | Proximity to Past Earthquakes                                            |
| EEPAS family     | EEPASfull    | Every Earthquake a Precursor According to Scale, mixed with PPE          |
| Hybrid           | GSSGSRM      | The SUP baseline modulated by the GSRM strain-rate alarm                 |

The forecasts give the expected number of M ≥ 7.45 earthquakes per year in 16 magnitude
bins from 7.45 to 8.95 (the last bin is open-ended), at depths of 0–70 km. The
EEPAS-family and GSSGSRM forecasts are fitted on data before 2014 only.

![The nine forecasts on SN10L11: rate density on a common logarithmic scale.](about/rate_density_maps.png)

## Tests

- **N-test:** the total number of events.
- **M-test:** the magnitude distribution.
- **S-test:** the spatial distribution.
- **CL-test:** space and magnitude together (conditional likelihood).
- **T-test:** the information gain per earthquake over GEAR1 *on the same grid*, with
  its 95% confidence interval.

The target events are the 30 gCMT earthquakes of M ≥ 7.45, at most 70 km deep, in
[2014-01-01, 2022-01-01). The likelihood tests simulate 10,000 catalogues with a fixed
seed. A forecast is rejected when its quantile is below 0.05, or, for the two-sided
N-test, when either tail probability is below 0.025. The eight quadtree grids are
correlated views of the same forecasts, not independent replications.

## In this dashboard

- **Overview:** a map of every quadtree grid.
- **Forecasts:** every model on every grid, as expected events per cell or per 10⁴ km².
- **Results, Charts:** the test scores as heatmaps, models × grids (the native 0.1°
  grid included) and models × years for any grid, the native one too.
- **Results, Figures:** the plots of every test, and the summary figures of the
  experiment.
