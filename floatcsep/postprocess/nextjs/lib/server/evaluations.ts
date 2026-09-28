import crypto from 'crypto';
import fs from 'fs/promises';
import path from 'path';
import type { EvaluationFile, EvaluationSummary } from '@/lib/types';
import type { LoadedManifest } from './manifest';

/**
 * Condenses saved pyCSEP evaluation results for the charts. Results of
 * simulation-based tests embed every simulated statistic (often 10,000 values),
 * so each file is summarized once and cached by path, size and mtime.
 */

const ALPHA = 0.05;
const CACHE_VERSION = 2;

type Raw = Record<string, any>;

interface CacheEntry {
  mtimeMs: number;
  size: number;
  summary: Omit<EvaluationSummary, 'window' | 'test' | 'model'>;
}

let memory: Record<string, CacheEntry> | null = null;

const cacheFile = () =>
  path.join(
    process.env.FLOATCSEP_DASHBOARD_CACHE || path.join(process.cwd(), '.cache', 'data'),
    'evaluation-summaries.json',
  );

async function readCache(): Promise<Record<string, CacheEntry>> {
  if (memory) return memory;
  try {
    const stored = JSON.parse(await fs.readFile(cacheFile(), 'utf-8'));
    memory = stored.version === CACHE_VERSION ? stored.entries : {};
  } catch {
    memory = {};
  }
  return memory!;
}

async function writeCache(entries: Record<string, CacheEntry>) {
  try {
    await fs.mkdir(path.dirname(cacheFile()), { recursive: true });
    const tmp = `${cacheFile()}.${process.pid}.tmp`;
    await fs.writeFile(tmp, JSON.stringify({ version: CACHE_VERSION, entries }));
    await fs.rename(tmp, cacheFile());
  } catch (error) {
    console.error('[dashboard] Could not write the evaluation cache', error);
  }
}

/* ------------------------------------------------------------- statistics */

/** Inverse standard normal CDF (Acklam's rational approximation). */
function normalQuantile(p: number): number {
  const a = [
    -39.69683028665376, 220.9460984245205, -275.9285104469687, 138.357751867269, -30.66479806614716, 2.506628277459239,
  ];
  const b = [-54.47609879822406, 161.5858368580409, -155.6989798598866, 66.80131188771972, -13.28068155288572];
  const c = [
    -0.007784894002430293, -0.3223964580411365, -2.400758277161838, -2.549732539343734, 4.374664141464968,
    2.938163982698783,
  ];
  const d = [0.007784695709041462, 0.3224671290700398, 2.445134137142996, 3.754408661907416];
  const low = 0.02425;
  if (p < low) {
    const q = Math.sqrt(-2 * Math.log(p));
    return (
      (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) /
      ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    );
  }
  if (p > 1 - low) return -normalQuantile(1 - p);
  const q = p - 0.5;
  const r = q * q;
  return (
    ((((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q) /
    (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)
  );
}

/** Smallest k with P(X <= k) >= p for X ~ Poisson(mean) (as scipy's poisson.ppf). */
function poissonQuantile(p: number, mean: number): number {
  if (!(mean > 0)) return 0;
  if (mean > 500) return Math.max(0, Math.round(mean + normalQuantile(p) * Math.sqrt(mean)));
  let k = 0;
  let pmf = Math.exp(-mean);
  let cdf = pmf;
  while (cdf < p - 1e-12 && k < 1e6) {
    k += 1;
    pmf *= mean / k;
    cdf += pmf;
  }
  return k;
}

/** Percentile with linear interpolation (numpy's default). */
function percentile(sorted: Float64Array, q: number): number {
  const pos = (q / 100) * (sorted.length - 1);
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

const finite = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);

/** The finite numbers among `values` (NaN results are read as null, see parseResult). */
const finiteValues = (values: unknown[]): number[] =>
  values.filter((v): v is number => typeof v === 'number' && Number.isFinite(v));

/**
 * Python's json module writes NaN, Infinity and -Infinity (a T-test with a
 * single event, a zero rate where an event occurred), which JSON.parse rejects.
 * Outside strings, NaN is read as null and the infinities as ±1e999, which
 * JSON.parse turns into ±Infinity.
 */
export function parseResult(text: string): Raw {
  try {
    return JSON.parse(text);
  } catch (error) {
    if (!/NaN|Infinity/.test(text)) throw error;
    return JSON.parse(
      text.replace(/"(?:[^"\\]|\\.)*"|-?Infinity|NaN/g, (token) =>
        token[0] === '"' ? token : token === 'NaN' ? 'null' : token[0] === '-' ? '-1e999' : '1e999',
      ),
    );
  }
}

/** Condense one EvaluationResult dictionary. */
export function summarize(result: Raw): CacheEntry['summary'] {
  const name = String(result.name ?? '');
  const observedRaw = result.observed_statistic;
  const distribution = result.test_distribution;
  const quantileRaw = result.quantile;
  const base = {
    name,
    observed: finite(observedRaw),
    quantile: null as number | null,
    interval: null as [number, number] | null,
    expected: null as number | null,
    reference: null as string | null,
    passed: null as boolean | null,
    series: null as number[] | null,
  };

  if (Array.isArray(observedRaw)) {
    return { ...base, kind: 'sequential', series: observedRaw.map((v) => (typeof v === 'number' ? v : NaN)) };
  }

  const comparative = Array.isArray(result.sim_name) || /\b(T|W)-Test/i.test(name);
  if (comparative) {
    const bounds = Array.isArray(distribution) ? finiteValues(distribution) : [];
    const [lower, upper] = bounds.length === 2 ? [Math.min(...bounds), Math.max(...bounds)] : [NaN, NaN];
    const reference = Array.isArray(result.sim_name) ? String(result.sim_name[1] ?? '') : null;
    const ok = Number.isFinite(lower) && Number.isFinite(upper);
    return {
      ...base,
      kind: 'comparative',
      reference,
      interval: ok ? [lower, upper] : null,
      // Significantly better (true), worse (false), or indistinguishable (null).
      passed: ok ? (lower > 0 ? true : upper < 0 ? false : null) : base.observed === null ? false : null,
    };
  }

  if (/N-Test/i.test(name) && Array.isArray(distribution) && distribution[0] === 'poisson') {
    const mean = finite(distribution[1]);
    const deltas = finiteValues(Array.isArray(quantileRaw) ? quantileRaw : [quantileRaw]);
    const score = deltas.length ? Math.min(...deltas) : null;
    return {
      ...base,
      kind: 'number',
      quantile: score,
      expected: mean,
      interval: mean === null ? null : [poissonQuantile(ALPHA / 2, mean), poissonQuantile(1 - ALPHA / 2, mean)],
      // Two-sided: rejected when either tail probability is below alpha / 2.
      passed: score === null ? null : score >= ALPHA / 2,
    };
  }

  if (Array.isArray(distribution) && distribution.length > 2) {
    const values = Float64Array.from(finiteValues(distribution)).sort();
    const score = finite(Array.isArray(quantileRaw) ? quantileRaw[0] : quantileRaw);
    return {
      ...base,
      kind: 'consistency',
      quantile: score,
      expected: values.length ? percentile(values, 50) : null,
      // One-sided (lower): the 5th percentile to the largest simulated value.
      interval: values.length ? [percentile(values, 100 * ALPHA), values[values.length - 1]] : null,
      passed: score === null ? null : score >= ALPHA,
    };
  }

  return { ...base, kind: 'other', quantile: finite(Array.isArray(quantileRaw) ? quantileRaw[0] : quantileRaw) };
}

/** Summaries of every saved evaluation of the experiment. */
export async function evaluationSummaries(
  loaded: LoadedManifest,
): Promise<{ summaries: EvaluationSummary[]; etag: string }> {
  const cache = await readCache();
  const files: EvaluationFile[] = loaded.manifest.evaluations;
  const stats = await Promise.all(
    files.map((file) => fs.stat(path.resolve(loaded.appRoot, file.path)).catch(() => null)),
  );

  let changed = false;
  const summaries: EvaluationSummary[] = [];
  const signature = crypto.createHash('sha1');
  // Parse in small batches: the files can add up to hundreds of megabytes.
  const BATCH = 16;
  for (let start = 0; start < files.length; start += BATCH) {
    const batch = files.slice(start, start + BATCH).map(async (file, offset) => {
      const stat = stats[start + offset];
      if (!stat) return null;
      const absolute = path.resolve(loaded.appRoot, file.path);
      signature.update(`${absolute}:${stat.mtimeMs}:${stat.size};`);
      const hit = cache[absolute];
      if (hit && hit.mtimeMs === stat.mtimeMs && hit.size === stat.size) {
        return { ...file, ...hit.summary } as EvaluationSummary;
      }
      try {
        const summary = summarize(parseResult(await fs.readFile(absolute, 'utf-8')));
        cache[absolute] = { mtimeMs: stat.mtimeMs, size: stat.size, summary };
        changed = true;
        return { ...file, ...summary } as EvaluationSummary;
      } catch (error) {
        console.error(`[dashboard] Unreadable evaluation ${file.path}`, error);
        return null;
      }
    });
    for (const item of await Promise.all(batch)) if (item) summaries.push(item);
  }
  if (changed) await writeCache(cache);
  return { summaries, etag: `"${signature.digest('hex')}"` };
}
