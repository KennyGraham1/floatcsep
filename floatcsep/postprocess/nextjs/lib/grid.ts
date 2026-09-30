/**
 * Spatial grids of forecasts and regions, in two layouts:
 *
 * - "regular": cells of `dh` degrees addressed by integer column/row (ix, iy)
 *   from the lower-left corner (lon0, lat0) — pyCSEP CartesianGrid2D;
 * - "quadtree": Web Mercator tiles addressed by Bing quadkeys, of any zoom
 *   level (multi-resolution) — pyCSEP QuadtreeGrid2D.
 */
import type { ForecastPayload, Region } from './types';

const EARTH_RADIUS_KM = 6371.0088;
const MAX_LAT = 85.05112878;
const RAD = Math.PI / 180;

export interface RegularGrid {
  type: 'regular';
  n: number;
  lon0: number;
  lat0: number;
  dh: number;
  nx: number;
  ny: number;
  ix: ArrayLike<number>;
  iy: ArrayLike<number>;
  /** Cell index at row * nx + col, or -1. */
  lookup: Int32Array;
}

export interface QuadtreeGrid {
  type: 'quadtree';
  n: number;
  quadkeys: string[];
  /** Zoom levels present, ascending. */
  levels: number[];
  index: Map<string, number>;
  /** Quadkeys in lexicographic order (each subtree is a contiguous range). */
  sorted: string[];
  /** Cell index of each entry of `sorted`. */
  order: Int32Array;
}

export type CellGrid = RegularGrid | QuadtreeGrid;

/* ------------------------------------------------------------ Web Mercator */

export function tileToLon(x: number, z: number): number {
  return (x / 2 ** z) * 360 - 180;
}

export function tileToLat(y: number, z: number): number {
  const n = Math.PI * (1 - (2 * y) / 2 ** z);
  return Math.atan(Math.sinh(n)) / RAD;
}

export function lonToTile(lon: number, z: number): number {
  const wrapped = ((((lon + 180) % 360) + 360) % 360) - 180;
  return Math.min(2 ** z - 1, Math.floor(((wrapped + 180) / 360) * 2 ** z));
}

export function latToTile(lat: number, z: number): number {
  const phi = Math.min(MAX_LAT, Math.max(-MAX_LAT, lat)) * RAD;
  const y = ((1 - Math.log(Math.tan(phi) + 1 / Math.cos(phi)) / Math.PI) / 2) * 2 ** z;
  return Math.min(2 ** z - 1, Math.max(0, Math.floor(y)));
}

/** Bing quadkey of tile (x, y) at zoom z. */
export function tileToQuadkey(x: number, y: number, z: number): string {
  let key = '';
  for (let i = z; i > 0; i--) {
    const mask = 1 << (i - 1);
    key += String((x & mask ? 1 : 0) + (y & mask ? 2 : 0));
  }
  return key;
}

export function quadkeyToTile(quadkey: string): { x: number; y: number; z: number } {
  let x = 0;
  let y = 0;
  for (let i = 0; i < quadkey.length; i++) {
    const digit = quadkey.charCodeAt(i) - 48;
    x = x * 2 + (digit & 1);
    y = y * 2 + (digit >> 1);
  }
  return { x, y, z: quadkey.length };
}

/* ---------------------------------------------------------------- building */

export function regularGrid(
  lon0: number,
  lat0: number,
  dh: number,
  nx: number,
  ny: number,
  ix: ArrayLike<number>,
  iy: ArrayLike<number>,
): RegularGrid {
  const lookup = new Int32Array(nx * ny).fill(-1);
  for (let k = 0; k < ix.length; k++) lookup[iy[k] * nx + ix[k]] = k;
  return { type: 'regular', n: ix.length, lon0, lat0, dh, nx, ny, ix, iy, lookup };
}

/** Every cell of a regular grid, in longitude-major order: cell k = column * ny + row. */
export function denseGrid(lon0: number, lat0: number, dh: number, nx: number, ny: number): RegularGrid {
  const n = nx * ny;
  const ix = new Uint16Array(n);
  const iy = new Uint16Array(n);
  const lookup = new Int32Array(n);
  let k = 0;
  for (let col = 0; col < nx; col++) {
    for (let row = 0; row < ny; row++, k++) {
      ix[k] = col;
      iy[k] = row;
      lookup[row * nx + col] = k;
    }
  }
  return { type: 'regular', n, lon0, lat0, dh, nx, ny, ix, iy, lookup };
}

export function quadtreeGrid(quadkeys: string[]): QuadtreeGrid {
  const index = new Map<string, number>();
  const levels = new Set<number>();
  quadkeys.forEach((q, k) => {
    index.set(q, k);
    levels.add(q.length);
  });
  const orderArray = quadkeys.map((_, k) => k).sort((a, b) => (quadkeys[a] < quadkeys[b] ? -1 : 1));
  return {
    type: 'quadtree',
    n: quadkeys.length,
    quadkeys,
    levels: Array.from(levels).sort((a, b) => a - b),
    index,
    sorted: orderArray.map((k) => quadkeys[k]),
    order: Int32Array.from(orderArray),
  };
}

/** The experiment region's cells as a regular grid. */
export function regionGrid(region: Region | null): RegularGrid | null {
  const origins = region?.origins;
  const dh = region?.dh;
  if (!origins || origins.length === 0 || !dh) return null;

  const lons = origins.map(([lon]) => lon);
  let min = Infinity;
  let max = -Infinity;
  for (const lon of lons) {
    if (lon < min) min = lon;
    if (lon > max) max = lon;
  }
  // Keep regions around the antimeridian contiguous (as manifest_api.py does).
  if (max - min > 180) {
    const shifted = lons.map((lon) => (lon < 0 ? lon + 360 : lon));
    let sMin = Infinity;
    let sMax = -Infinity;
    for (const lon of shifted) {
      if (lon < sMin) sMin = lon;
      if (lon > sMax) sMax = lon;
    }
    if (sMax - sMin < max - min) {
      shifted.forEach((lon, i) => (lons[i] = lon));
      min = sMin;
    }
  }

  let lat0 = Infinity;
  for (const [, lat] of origins) if (lat < lat0) lat0 = lat;
  const n = origins.length;
  const ix = new Int32Array(n);
  const iy = new Int32Array(n);
  let nx = 0;
  let ny = 0;
  for (let k = 0; k < n; k++) {
    ix[k] = Math.round((lons[k] - min) / dh);
    iy[k] = Math.round((origins[k][1] - lat0) / dh);
    if (ix[k] + 1 > nx) nx = ix[k] + 1;
    if (iy[k] + 1 > ny) ny = iy[k] + 1;
  }
  return regularGrid(min, lat0, dh, nx, ny, ix, iy);
}

export interface ForecastCells {
  grid: CellGrid;
  /** Expected events per cell in the time window. */
  rates: Float64Array;
  /** Cell areas in km². */
  areas: Float64Array;
}

export function forecastCells(forecast: ForecastPayload): ForecastCells {
  if (forecast.grid === 'dense') {
    const grid = denseGrid(forecast.lon0!, forecast.lat0!, forecast.dh!, forecast.nx!, forecast.ny!);
    const data = forecast.rateData;
    const scale = forecast.rate_scale ?? 1;
    const rates = new Float64Array(grid.n);
    if (data && data.length === grid.n) for (let k = 0; k < grid.n; k++) rates[k] = data[k] * scale;
    // Cells k < ny are the first column, one per row; every row shares its area.
    const rowAreas = Float64Array.from({ length: grid.ny }, (_, row) => cellArea(grid, row));
    const areas = new Float64Array(grid.n);
    for (let k = 0; k < grid.n; k++) areas[k] = rowAreas[k % grid.ny];
    return { grid, rates, areas };
  }
  const grid =
    forecast.grid === 'quadtree'
      ? quadtreeGrid(forecast.quadkeys ?? [])
      : regularGrid(
          forecast.lon0!,
          forecast.lat0!,
          forecast.dh!,
          forecast.nx!,
          forecast.ny!,
          forecast.ix!,
          forecast.iy!,
        );
  const rates = Float64Array.from(forecast.rate);
  const areas = new Float64Array(grid.n);
  for (let k = 0; k < grid.n; k++) areas[k] = cellArea(grid, k);
  return { grid, rates, areas };
}

/* ------------------------------------------------------------- cell queries */

/** [west, south, east, north] of cell k, in degrees. */
export function cellBounds(grid: CellGrid, k: number): [number, number, number, number] {
  if (grid.type === 'regular') {
    const west = grid.lon0 + grid.ix[k] * grid.dh;
    const south = grid.lat0 + grid.iy[k] * grid.dh;
    return [west, south, west + grid.dh, south + grid.dh];
  }
  const { x, y, z } = quadkeyToTile(grid.quadkeys[k]);
  return [tileToLon(x, z), tileToLat(y + 1, z), tileToLon(x + 1, z), tileToLat(y, z)];
}

/** Spherical area of cell k in km². */
export function cellArea(grid: CellGrid, k: number): number {
  const [west, south, east, north] = cellBounds(grid, k);
  return EARTH_RADIUS_KM ** 2 * (east - west) * RAD * (Math.sin(north * RAD) - Math.sin(south * RAD));
}

/** [south, west, north, east] covering all cells. */
export function gridExtent(grid: CellGrid): [number, number, number, number] {
  if (grid.type === 'regular') {
    return [grid.lat0, grid.lon0, grid.lat0 + grid.ny * grid.dh, grid.lon0 + grid.nx * grid.dh];
  }
  let s = Infinity;
  let w = Infinity;
  let n = -Infinity;
  let e = -Infinity;
  for (let k = 0; k < grid.n; k++) {
    const [west, south, east, north] = cellBounds(grid, k);
    if (south < s) s = south;
    if (west < w) w = west;
    if (north > n) n = north;
    if (east > e) e = east;
  }
  return [s, w, n, e];
}

/**
 * The extent to show a grid with: grids covering the globe are shown
 * Pacific-centred (longitudes 0 to 360), as global seismicity usually is.
 */
export function viewExtent(extent: [number, number, number, number]): [number, number, number, number] {
  const [south, west, north, east] = extent;
  return east - west >= 300 ? [south, 0, north, 360] : extent;
}

/** Index of the cell containing (lon, lat), or -1. */
export function cellAt(grid: CellGrid, lon: number, lat: number): number {
  if (grid.type === 'regular') {
    let x = lon;
    while (x < grid.lon0) x += 360;
    while (x >= grid.lon0 + 360) x -= 360;
    const col = Math.floor((x - grid.lon0) / grid.dh);
    const row = Math.floor((lat - grid.lat0) / grid.dh);
    if (col < 0 || col >= grid.nx || row < 0 || row >= grid.ny) return -1;
    return grid.lookup[row * grid.nx + col];
  }
  if (Math.abs(lat) > MAX_LAT) return -1;
  const deepest = grid.levels[grid.levels.length - 1];
  const x = ((((lon + 180) % 360) + 360) % 360) - 180;
  const key = tileToQuadkey(lonToTile(x, deepest), latToTile(lat, deepest), deepest);
  for (const level of grid.levels) {
    const k = grid.index.get(key.slice(0, level));
    if (k !== undefined) return k;
  }
  return -1;
}

/** First index in `sorted` whose value is >= `key`. */
export function lowerBound(sorted: string[], key: string): number {
  let lo = 0;
  let hi = sorted.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (sorted[mid] < key) lo = mid + 1;
    else hi = mid;
  }
  return lo;
}

/** A single-colour lookup table (every value maps to `hex`). */
export function solidTable(hex: string): Uint8ClampedArray {
  const n = parseInt(hex.slice(1), 16);
  const table = new Uint8ClampedArray(256 * 3);
  for (let i = 0; i < 256; i++) {
    table[i * 3] = (n >> 16) & 255;
    table[i * 3 + 1] = (n >> 8) & 255;
    table[i * 3 + 2] = n & 255;
  }
  return table;
}
