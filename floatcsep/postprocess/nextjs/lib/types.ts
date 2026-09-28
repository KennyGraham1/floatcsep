/**
 * Data shapes shared by the API routes and the pages.
 *
 * The manifest served by /api/manifest is a normalized version of the file that
 * `floatcsep view` writes (see lib/server/manifest.ts): paths are relative to the
 * experiment's results directory and only files that exist are listed.
 */

export interface Region {
  name: string | null;
  /** [west, south, east, north] in degrees. */
  bbox: [number, number, number, number] | null;
  dh: number | null;
  /** Lower-left corners of the grid cells, as [lon, lat]. */
  origins: [number, number][] | null;
}

export interface Model {
  name: string;
  forecast_unit: string | null;
  path: string | null;
  giturl: string | null;
  git_hash: string | null;
  zenodo_id: string | number | null;
  authors: string | null;
  doi: string | null;
  func: string | null;
  func_kwargs: Record<string, unknown> | null;
  fmt: string | null;
  forecast_class: string | null;
  is_catalog_forecast: boolean;
  /** Forecast file per time window (same order as `time_windows`), or null. */
  forecasts: (string | null)[];
  /** Whether each forecast file exists on disk. */
  forecast_available: boolean[];
}

export interface Test {
  name: string;
  func: string | null;
  func_kwargs: Record<string, unknown> | null;
  ref_model: string | null;
  plot_func: string[];
  plot_args: unknown;
  plot_kwargs: unknown;
}

/** A result figure. `model` is null for the test's summary figure. */
export interface ResultFigure {
  window: number;
  test: string;
  model: string | null;
  path: string;
}

/** A saved evaluation result (pyCSEP EvaluationResult JSON). */
export interface EvaluationFile {
  window: number;
  test: string;
  model: string;
  path: string;
}

/** A figure made for the whole experiment (e.g. by a plot_custom script). */
export interface SummaryFigure {
  name: string;
  path: string;
}

export interface CatalogInfo {
  path: string | null;
  available: boolean;
}

export interface Manifest {
  name: string;
  start_date: string;
  end_date: string;
  authors: string | null;
  doi: string | null;
  journal: string | null;
  manuscript_doi: string | null;
  exp_time: string | null;
  floatcsep_version: string | null;
  pycsep_version: string | null;
  last_run: string | null;
  catalog_doi: string | null;
  license: string | null;
  magnitudes: number[];
  region: Region | null;
  models: Model[];
  tests: Test[];
  time_windows: string[];
  catalog: CatalogInfo;
  results: ResultFigure[];
  evaluations: EvaluationFile[];
  summary_figures: SummaryFigure[];
  /** about.md describing the experiment (relative to the results folder), if present. */
  about: string | null;
  exp_class: string | null;
  n_intervals: number | null;
  horizon: string | null;
  offset: string | null;
  growth: string | null;
  mag_min: number | null;
  mag_max: number | null;
  mag_bin: number | null;
  depth_min: number | null;
  depth_max: number | null;
  run_mode: string | null;
  run_dir: string | null;
  config_file: string | null;
  model_config: string | null;
  test_config: string | null;
}

/** Observed catalog, column-oriented. `time` is epoch milliseconds (UTC). */
export interface CatalogPayload {
  version: number;
  count: number;
  lon: number[];
  lat: number[];
  mag: number[];
  depth: (number | null)[];
  time: number[];
  id: string[];
}

/**
 * Expected events of one forecast in its time window, for the cells with a
 * positive rate. Cells are either on a regular grid of spacing `dh` (integer
 * positions `ix`, `iy` from the lower-left corner `lon0`, `lat0`) or quadtree
 * tiles given by their quadkeys.
 */
export interface ForecastPayload {
  version: number;
  kind: 'gridded' | 'catalog';
  grid: 'regular' | 'quadtree';
  model: string;
  time_window: string;
  path: string;
  dh?: number;
  lon0?: number;
  lat0?: number;
  nx?: number;
  ny?: number;
  ix?: number[];
  iy?: number[];
  quadkeys?: string[];
  n_cells: number;
  n_active: number;
  rate: number[];
  total: number;
  /** log10 of the smallest / largest positive cell rate. */
  vmin: number;
  vmax: number;
  magnitudes: (number | null)[];
  magnitude_rates: number[];
  n_catalogs: number | null;
}

/**
 * One evaluation result, condensed for charts:
 * - "number": N-test; `interval` is the 95% range of Poisson(`expected`);
 * - "consistency": M/S/CL/L tests; `interval` is the 2.5–97.5% range of the
 *   simulated statistic;
 * - "comparative": T/W-tests against `reference`; `interval` is the 95% CI of
 *   the information gain (`observed`);
 * - "sequential": one value per time window (`series`).
 */
export interface EvaluationSummary {
  window: number;
  test: string;
  model: string;
  name: string;
  kind: 'number' | 'consistency' | 'comparative' | 'sequential' | 'other';
  observed: number | null;
  quantile: number | null;
  interval: [number, number] | null;
  expected: number | null;
  reference: string | null;
  /** true = not rejected / significantly better; false = rejected / worse. */
  passed: boolean | null;
  series: number[] | null;
}

export interface ApiErrorBody {
  error: string;
  details?: string;
}
