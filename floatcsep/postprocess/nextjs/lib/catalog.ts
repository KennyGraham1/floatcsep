import type { CatalogPayload, Region } from './types';
import type { TimeWindow } from './time';

/** Event classes: before the experiment start (input) or during it (test). */
export const INPUT = 0;
export const TEST = 1;

export interface Catalog {
  n: number;
  lon: Float64Array;
  lat: Float64Array;
  mag: Float64Array;
  /** NaN where unknown. */
  depth: Float64Array;
  /** Epoch milliseconds (UTC). */
  time: Float64Array;
  id: string[];
  /** INPUT or TEST per event. */
  kind: Uint8Array;
}

export function toCatalog(payload: CatalogPayload, startMs: number): Catalog {
  const n = payload.count;
  const time = Float64Array.from(payload.time);
  const kind = new Uint8Array(n);
  for (let i = 0; i < n; i++) kind[i] = Number.isFinite(startMs) && time[i] < startMs ? INPUT : TEST;
  return {
    n,
    lon: Float64Array.from(payload.lon),
    lat: Float64Array.from(payload.lat),
    mag: Float64Array.from(payload.mag),
    depth: Float64Array.from(payload.depth, (d) => (d === null ? NaN : d)),
    time,
    id: payload.id,
    kind,
  };
}

export interface CatalogFilter {
  input: boolean;
  test: boolean;
  minMagnitude: number;
}

/** Indices of events passing the filter, in catalog order. */
export function filterEvents(catalog: Catalog, filter: CatalogFilter): Uint32Array {
  const out: number[] = [];
  for (let i = 0; i < catalog.n; i++) {
    const kindOk = catalog.kind[i] === INPUT ? filter.input : filter.test;
    if (kindOk && catalog.mag[i] >= filter.minMagnitude - 1e-9) out.push(i);
  }
  return Uint32Array.from(out);
}

export interface MagnitudeFrequency {
  /** Lower bin edges. */
  magnitudes: number[];
  incremental: number[];
  /** Number of events with magnitude >= the bin edge. */
  cumulative: number[];
}

export function magnitudeFrequency(
  mags: ArrayLike<number>,
  indices: ArrayLike<number>,
  binWidth = 0.1,
): MagnitudeFrequency {
  if (indices.length === 0) return { magnitudes: [], incremental: [], cumulative: [] };
  const bins = new Map<number, number>();
  let lo = Infinity;
  let hi = -Infinity;
  for (let j = 0; j < indices.length; j++) {
    const b = Math.floor(mags[indices[j]] / binWidth + 1e-6);
    bins.set(b, (bins.get(b) ?? 0) + 1);
    if (b < lo) lo = b;
    if (b > hi) hi = b;
  }
  const magnitudes: number[] = [];
  const incremental: number[] = [];
  for (let b = lo; b <= hi; b++) {
    magnitudes.push(Number((b * binWidth).toFixed(4)));
    incremental.push(bins.get(b) ?? 0);
  }
  const cumulative = new Array<number>(incremental.length);
  let running = 0;
  for (let k = incremental.length - 1; k >= 0; k--) {
    running += incremental[k];
    cumulative[k] = running;
  }
  return { magnitudes, incremental, cumulative };
}

export interface BValue {
  b: number;
  /** Standard error (Shi & Bolt, 1982). */
  sigma: number;
  n: number;
  completeness: number;
}

/**
 * Maximum-likelihood Gutenberg–Richter b-value (Aki, 1965; Utsu binning
 * correction) of the events at or above the completeness magnitude.
 */
export function bValue(
  mags: ArrayLike<number>,
  indices: ArrayLike<number>,
  completeness: number,
  binWidth = 0.1,
): BValue | null {
  const values: number[] = [];
  for (let j = 0; j < indices.length; j++) {
    const m = mags[indices[j]];
    if (m >= completeness - 1e-9) values.push(m);
  }
  const n = values.length;
  if (n < 30) return null;
  const mean = values.reduce((sum, m) => sum + m, 0) / n;
  const denominator = mean - (completeness - binWidth / 2);
  if (denominator <= 0) return null;
  const b = Math.LOG10E / denominator;
  const variance = values.reduce((sum, m) => sum + (m - mean) ** 2, 0) / (n * (n - 1));
  return { b, sigma: 2.3 * b * b * Math.sqrt(variance), n, completeness };
}

/** Number of events inside each time window ([start, end)). */
export function countPerWindow(catalog: Catalog, indices: ArrayLike<number>, windows: TimeWindow[]): number[] {
  const counts = windows.map(() => 0);
  for (let j = 0; j < indices.length; j++) {
    const t = catalog.time[indices[j]];
    for (let w = 0; w < windows.length; w++) {
      if (t >= windows[w].start && t < windows[w].end) counts[w]++;
    }
  }
  return counts;
}

/** Point-in-grid test for the experiment's region (the cells in its origins). */
export interface RegionMask {
  contains(lon: number, lat: number): boolean;
}

export function regionMask(region: Region | null): RegionMask | null {
  const origins = region?.origins;
  const dh = region?.dh;
  if (!origins || origins.length === 0 || !dh) return null;
  let lon0 = Infinity;
  let lat0 = Infinity;
  for (const [lon, lat] of origins) {
    if (lon < lon0) lon0 = lon;
    if (lat < lat0) lat0 = lat;
  }
  const cells = new Set<number>();
  const key = (ix: number, iy: number) => iy * 1_000_003 + ix;
  for (const [lon, lat] of origins) {
    cells.add(key(Math.round((lon - lon0) / dh), Math.round((lat - lat0) / dh)));
  }
  return {
    contains(lon: number, lat: number) {
      const iy = Math.floor((lat - lat0) / dh + 1e-9);
      for (const shift of [0, 360, -360]) {
        const ix = Math.floor((lon + shift - lon0) / dh + 1e-9);
        if (ix >= 0 && iy >= 0 && cells.has(key(ix, iy))) return true;
      }
      return false;
    },
  };
}

/** Events of a time window above a magnitude floor, optionally inside the region. */
export function eventsInWindow(
  catalog: Catalog,
  window: TimeWindow,
  minMagnitude: number,
  mask: RegionMask | null,
): Uint32Array {
  const out: number[] = [];
  for (let i = 0; i < catalog.n; i++) {
    const t = catalog.time[i];
    if (t < window.start || t >= window.end) continue;
    if (catalog.mag[i] < minMagnitude - 1e-9) continue;
    if (mask && !mask.contains(catalog.lon[i], catalog.lat[i])) continue;
    out.push(i);
  }
  return Uint32Array.from(out);
}
