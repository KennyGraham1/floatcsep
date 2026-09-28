import type { GridRaster } from '@/components/maps/RasterLayer';
import type { ForecastPayload, Region } from './types';

/** The experiment region's cells as a raster (value 1 everywhere). */
export function regionRaster(region: Region | null): GridRaster | null {
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
  const lon0 = min;
  const n = origins.length;
  const ix = new Int32Array(n);
  const iy = new Int32Array(n);
  let nx = 0;
  let ny = 0;
  for (let k = 0; k < n; k++) {
    ix[k] = Math.round((lons[k] - lon0) / dh);
    iy[k] = Math.round((origins[k][1] - lat0) / dh);
    if (ix[k] + 1 > nx) nx = ix[k] + 1;
    if (iy[k] + 1 > ny) ny = iy[k] + 1;
  }
  return { lon0, lat0, dh, nx, ny, ix, iy, values: new Float32Array(n).fill(1) };
}

/** A forecast's active cells as a raster of log10 rates. */
export function forecastRaster(forecast: ForecastPayload): GridRaster & { rates: Float64Array } {
  const rates = Float64Array.from(forecast.rate);
  const values = new Float64Array(rates.length);
  for (let k = 0; k < rates.length; k++) values[k] = Math.log10(rates[k]);
  return {
    lon0: forecast.lon0,
    lat0: forecast.lat0,
    dh: forecast.dh,
    nx: forecast.nx,
    ny: forecast.ny,
    ix: forecast.ix,
    iy: forecast.iy,
    values,
    rates,
  };
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
