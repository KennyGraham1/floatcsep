import fs from 'fs/promises';
import path from 'path';
import { HttpError } from './http';
import type { EvaluationFile, Manifest, Model, Region, ResultFigure, SummaryFigure, Test } from '@/lib/types';

/** The manifest plus server-side facts the API routes need. */
export interface LoadedManifest {
  manifest: Manifest;
  manifestPath: string;
  /** Absolute directory that manifest paths are relative to. */
  appRoot: string;
  /** Relative paths of the figures the results route may serve. */
  figures: Set<string>;
}

type Raw = Record<string, any>;

let cached: { key: string; folders: string; value: LoadedManifest } | null = null;

/**
 * Modification times of the folders whose files the manifest lists (results and
 * figures): results written while the dashboard runs are then picked up.
 */
async function folderSignature({ manifest, appRoot }: LoadedManifest): Promise<string> {
  const windows = manifest.time_windows.map((tw) => path.join(appRoot, tw.replace(/\s+to\s+/, '_')));
  const folders = [
    path.join(appRoot, 'figures'),
    ...windows.flatMap((w) => [path.join(w, 'evaluations'), path.join(w, 'figures')]),
  ];
  const times = await Promise.all(
    folders.map((f) =>
      fs.stat(f).then(
        (s) => s.mtimeMs,
        () => 0,
      ),
    ),
  );
  return times.join(',');
}

/** Read and normalize the manifest written by `floatcsep view` (cached while it and the results are unchanged). */
export async function loadManifest(): Promise<LoadedManifest> {
  const manifestPath = process.env.MANIFEST_PATH;
  if (!manifestPath) {
    throw new HttpError(
      500,
      'The dashboard was started without an experiment',
      'MANIFEST_PATH is not set. Launch it with `floatcsep view <config> --ui nextjs`.',
    );
  }

  let stat;
  try {
    stat = await fs.stat(manifestPath);
  } catch {
    throw new HttpError(500, 'Experiment manifest not found', manifestPath);
  }

  const key = `${manifestPath}:${stat.mtimeMs}:${stat.size}`;
  if (cached?.key === key && cached.folders === (await folderSignature(cached.value))) return cached.value;

  let raw: Raw;
  try {
    raw = JSON.parse(await fs.readFile(manifestPath, 'utf-8'));
  } catch (error) {
    throw new HttpError(500, 'The experiment manifest could not be read', String(error));
  }

  const value = await normalizeManifest(raw, manifestPath);
  cached = { key, folders: await folderSignature(value), value };
  return value;
}

/** Resolve a manifest path (relative to the results directory) to an absolute path. */
export function resolveFromRoot(appRoot: string, relative: string): string {
  return path.resolve(appRoot, relative);
}

async function exists(file: string): Promise<boolean> {
  try {
    return (await fs.stat(file)).isFile();
  } catch {
    return false;
  }
}

const str = (value: unknown): string | null =>
  value === null || value === undefined || value === '' ? null : String(value);

const num = (value: unknown): number | null => (typeof value === 'number' && Number.isFinite(value) ? value : null);

function normalizeRegion(region: Raw | null | undefined): Region | null {
  if (!region || typeof region !== 'object') return null;
  let bbox: Region['bbox'] = null;
  if (Array.isArray(region.bbox) && region.bbox.length === 4) {
    // pyCSEP's get_bbox() is [min_lon, max_lon, min_lat, max_lat].
    const [minLon, maxLon, minLat, maxLat] = region.bbox.map(Number);
    bbox = [minLon, minLat, maxLon, maxLat];
  }
  return {
    name: str(region.name),
    bbox,
    dh: num(region.dh),
    origins: Array.isArray(region.origins) ? region.origins : null,
  };
}

/** Names of plot functions; older manifests stored functions as `{}`. */
function plotFunctionNames(value: unknown): string[] {
  const items = Array.isArray(value) ? value : value ? [value] : [];
  return items.filter((item): item is string => typeof item === 'string' && item.length > 0);
}

async function normalizeManifest(raw: Raw, manifestPath: string): Promise<LoadedManifest> {
  const appRoot = path.resolve(str(raw.app_root) ?? process.env.APP_ROOT ?? path.dirname(manifestPath));
  const timeWindows: string[] = Array.isArray(raw.time_windows) ? raw.time_windows.map(String) : [];
  const windowIndex = new Map(timeWindows.map((tw, i) => [tw, i]));
  const isFile = (relative: string) => exists(resolveFromRoot(appRoot, relative));

  const models: Model[] = await Promise.all(
    (Array.isArray(raw.models) ? raw.models : []).map(async (m: Raw) => {
      const forecasts = timeWindows.map((tw) => str(m.forecasts?.[tw]));
      const forecast_available = await Promise.all(forecasts.map((f) => (f ? isFile(f) : Promise.resolve(false))));
      return {
        name: String(m.name ?? 'Unnamed model'),
        forecast_unit: str(m.forecast_unit),
        path: str(m.path),
        giturl: str(m.giturl),
        git_hash: str(m.git_hash),
        zenodo_id: m.zenodo_id ?? null,
        authors: str(m.authors),
        doi: str(m.doi),
        func: str(m.func),
        func_kwargs: m.func_kwargs && typeof m.func_kwargs === 'object' ? m.func_kwargs : null,
        fmt: str(m.fmt),
        forecast_class: str(m.forecast_class),
        is_catalog_forecast: m.forecast_class === 'CatalogForecastRepository',
        forecasts,
        forecast_available,
      };
    }),
  );

  const tests: Test[] = (Array.isArray(raw.tests) ? raw.tests : []).map((t: Raw) => ({
    name: String(t.name ?? 'Unnamed test'),
    func: str(t.func),
    func_kwargs: t.func_kwargs && typeof t.func_kwargs === 'object' ? t.func_kwargs : null,
    ref_model: str(t.ref_model),
    plot_func: plotFunctionNames(t.plot_func),
    plot_args: t.plot_args ?? null,
    plot_kwargs: t.plot_kwargs ?? null,
  }));

  // Result figures, keyed "window|test" (summary) and "window|test|model".
  const candidates: ResultFigure[] = [];
  for (const [key, file] of Object.entries<string>(raw.results_main ?? {})) {
    const [tw, test] = key.split('|');
    const window = windowIndex.get(tw);
    if (window !== undefined && test && file) candidates.push({ window, test, model: null, path: file });
  }
  for (const [key, file] of Object.entries<string>(raw.results_model ?? {})) {
    const [tw, test, ...rest] = key.split('|');
    const window = windowIndex.get(tw);
    const model = rest.join('|');
    if (window !== undefined && test && model && file) candidates.push({ window, test, model, path: file });
  }
  const present = await Promise.all(candidates.map((figure) => isFile(figure.path)));
  const results = candidates.filter((_, i) => present[i]);

  // Saved evaluations follow floatCSEP's layout: <window>/evaluations/<test>_<model>.json
  const evaluationCandidates: EvaluationFile[] = [];
  timeWindows.forEach((tw, window) => {
    const folder = tw.replace(/\s+to\s+/, '_');
    for (const test of tests) {
      for (const model of models) {
        evaluationCandidates.push({
          window,
          test: test.name,
          model: model.name,
          path: path.posix.join(folder, 'evaluations', `${test.name}_${model.name}.json`),
        });
      }
    }
  });
  const evaluationPresent = await Promise.all(evaluationCandidates.map((e) => isFile(e.path)));
  const evaluations = evaluationCandidates.filter((_, i) => evaluationPresent[i]);

  // Results saved outside the configured tests (e.g. by a plot_custom script),
  // named <test>_<model>.json like floatCSEP's own. They are matched by model
  // first; results of models the experiment has no forecasts for (e.g. imported
  // from another grid) are then matched by a known test name.
  const known = new Set(evaluations.map((e) => e.path));
  const modelsByLength = [...models.map((m) => m.name)].sort((a, b) => b.length - a.length);
  const listings = await Promise.all(
    timeWindows.map(async (tw) => {
      const folder = path.posix.join(tw.replace(/\s+to\s+/, '_'), 'evaluations');
      const names = await fs.readdir(path.join(appRoot, folder)).catch(() => [] as string[]);
      return { folder, names };
    }),
  );
  const unmatched: { window: number; name: string; relative: string }[] = [];
  listings.forEach(({ folder, names }, window) => {
    for (const name of names) {
      const relative = path.posix.join(folder, name);
      if (!name.endsWith('.json') || known.has(relative)) continue;
      const model = modelsByLength.find((m) => name.endsWith(`_${m}.json`));
      const test = model ? name.slice(0, -`_${model}.json`.length) : '';
      if (model && test) evaluations.push({ window, test, model, path: relative });
      else unmatched.push({ window, name, relative });
    }
  });
  const testsByLength = [...new Set([...tests.map((t) => t.name), ...evaluations.map((e) => e.test)])].sort(
    (a, b) => b.length - a.length,
  );
  for (const { window, name, relative } of unmatched) {
    const test = testsByLength.find((t) => name.startsWith(`${t}_`));
    const model = test ? name.slice(test.length + 1, -'.json'.length) : '';
    if (test && model) evaluations.push({ window, test, model, path: relative });
  }

  // Figures for the whole experiment, e.g. written by a plot_custom script.
  let summaryFigures: SummaryFigure[] = [];
  try {
    const entries = await fs.readdir(path.join(appRoot, 'figures'), { withFileTypes: true });
    summaryFigures = entries
      .filter((e) => e.isFile() && /\.(png|jpe?g|svg|webp)$/i.test(e.name))
      .map((e) => ({ name: e.name, path: path.posix.join('figures', e.name) }))
      .sort((a, b) => a.name.localeCompare(b.name));
  } catch {
    // no summary figures
  }

  const catalogPath = str(raw.catalog?.path);
  const aboutPath = str(raw.about);

  const manifest: Manifest = {
    name: str(raw.name) ?? 'Experiment',
    start_date: String(raw.start_date ?? ''),
    end_date: String(raw.end_date ?? ''),
    authors: str(raw.authors),
    doi: str(raw.doi),
    journal: str(raw.journal),
    manuscript_doi: str(raw.manuscript_doi),
    exp_time: str(raw.exp_time),
    floatcsep_version: str(raw.floatcsep_version) ?? str(process.env.FLOATCSEP_VERSION),
    pycsep_version: str(raw.pycsep_version) ?? str(process.env.PYCSEP_VERSION),
    last_run: str(raw.last_run),
    catalog_doi: str(raw.catalog_doi),
    license: str(raw.license),
    magnitudes: Array.isArray(raw.magnitudes) ? raw.magnitudes.map(Number) : [],
    region: normalizeRegion(raw.region),
    models,
    tests,
    time_windows: timeWindows,
    catalog: {
      path: catalogPath,
      available: catalogPath ? await isFile(catalogPath) : false,
    },
    results,
    evaluations,
    summary_figures: summaryFigures,
    about: aboutPath && (await isFile(aboutPath)) ? aboutPath : null,
    exp_class: str(raw.exp_class),
    n_intervals: num(raw.n_intervals),
    horizon: str(raw.horizon),
    offset: str(raw.offset),
    growth: str(raw.growth),
    mag_min: num(raw.mag_min),
    mag_max: num(raw.mag_max),
    mag_bin: num(raw.mag_bin),
    depth_min: num(raw.depth_min),
    depth_max: num(raw.depth_max),
    run_mode: str(raw.run_mode),
    run_dir: str(raw.run_dir),
    config_file: str(raw.config_file),
    model_config: str(raw.model_config ?? raw.model_config_path),
    test_config: str(raw.test_config),
  };

  return {
    manifest,
    manifestPath,
    appRoot,
    figures: new Set([...results, ...summaryFigures].map((figure) => path.posix.normalize(figure.path))),
  };
}
