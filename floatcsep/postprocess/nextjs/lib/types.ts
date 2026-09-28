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
 * Expected rates of one forecast. Cells with a positive rate are listed by their
 * integer grid position (`ix`, `iy`) on a regular grid of spacing `dh` whose
 * lower-left cell corner is (`lon0`, `lat0`).
 */
export interface ForecastPayload {
  version: number;
  kind: 'gridded' | 'catalog';
  model: string;
  time_window: string;
  path: string;
  dh: number;
  lon0: number;
  lat0: number;
  nx: number;
  ny: number;
  n_cells: number;
  n_active: number;
  ix: number[];
  iy: number[];
  rate: number[];
  total: number;
  /** log10 of the smallest / largest positive cell rate. */
  vmin: number;
  vmax: number;
  magnitudes: (number | null)[];
  magnitude_rates: number[];
  n_catalogs: number | null;
}

export interface ApiErrorBody {
  error: string;
  details?: string;
}
