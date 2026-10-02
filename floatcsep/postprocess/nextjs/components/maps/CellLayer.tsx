'use client';

import L from 'leaflet';
import { useEffect, useMemo, useRef } from 'react';
import { useMap } from 'react-leaflet';
import {
  cellAt,
  lowerBound,
  tileToLat,
  tileToLon,
  tileToQuadkey,
  type CellGrid,
  type QuadtreeGrid,
  type RegularGrid,
} from '@/lib/grid';

const TILE = 256;
const MAX_LAT = 85.05112878;

const toMercator = (lat: number) => {
  const r = (Math.min(MAX_LAT, Math.max(-MAX_LAT, lat)) * Math.PI) / 180;
  return Math.log(Math.tan(Math.PI / 4 + r / 2));
};
const fromMercator = (y: number) => ((2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180) / Math.PI;

interface TileStyle {
  grid: CellGrid;
  /** Colour-table index (0–255) of each cell. */
  shade: Uint8Array;
  /** Cells without a value to draw (e.g. a zero rate, log10 = -Infinity), or null if none. */
  hidden: Uint8Array | null;
  table: Uint8ClampedArray;
  css: string[];
}

function buildStyle(
  grid: CellGrid,
  values: ArrayLike<number>,
  table: Uint8ClampedArray,
  domain: [number, number],
): TileStyle {
  const [lo, hi] = domain;
  const span = hi - lo || 1;
  const shade = new Uint8Array(grid.n);
  let hidden: Uint8Array | null = null;
  for (let k = 0; k < grid.n; k++) {
    if (!Number.isFinite(values[k])) {
      // Left transparent, as the cells that sparse grids leave out
      (hidden ??= new Uint8Array(grid.n))[k] = 1;
      continue;
    }
    const t = (values[k] - lo) / span;
    shade[k] = Math.round(Math.min(1, Math.max(0, t)) * 255);
  }
  const css = Array.from({ length: 256 }, (_, i) => `rgb(${table[i * 3]},${table[i * 3 + 1]},${table[i * 3 + 2]})`);
  return { grid, shade, hidden, table, css };
}

/** Quadtree cells are Web Mercator tiles: fill each cell's exact pixel square. */
function drawQuadtreeTile(ctx: CanvasRenderingContext2D, z: number, x: number, y: number, s: TileStyle) {
  const grid = s.grid as QuadtreeGrid;
  const key = tileToQuadkey(x, y, z);

  // A cell at this zoom or coarser covers the whole tile.
  for (const level of grid.levels) {
    if (level > z) break;
    const k = grid.index.get(key.slice(0, level));
    if (k !== undefined) {
      if (s.hidden?.[k]) return;
      ctx.fillStyle = s.css[s.shade[k]];
      ctx.fillRect(0, 0, TILE, TILE);
      return;
    }
  }

  // Finer cells inside the tile form a contiguous range of sorted quadkeys.
  const first = lowerBound(grid.sorted, key);
  const last = lowerBound(grid.sorted, `${key}4`);
  for (let i = first; i < last; i++) {
    const quadkey = grid.sorted[i];
    let dx = 0;
    let dy = 0;
    for (let j = z; j < quadkey.length; j++) {
      const digit = quadkey.charCodeAt(j) - 48;
      dx = dx * 2 + (digit & 1);
      dy = dy * 2 + (digit >> 1);
    }
    if (s.hidden?.[grid.order[i]]) continue;
    const size = TILE / 2 ** (quadkey.length - z);
    const px = Math.floor(dx * size);
    const py = Math.floor(dy * size);
    ctx.fillStyle = s.css[s.shade[grid.order[i]]];
    ctx.fillRect(px, py, Math.max(1, Math.ceil((dx + 1) * size) - px), Math.max(1, Math.ceil((dy + 1) * size) - py));
  }
}

/** Regular lon/lat cells: sample the cell under every pixel centre. */
function drawRegularTile(ctx: CanvasRenderingContext2D, z: number, x: number, y: number, s: TileStyle) {
  const grid = s.grid as RegularGrid;
  const west = tileToLon(x, z);
  const east = tileToLon(x + 1, z);
  const mercNorth = toMercator(tileToLat(y, z));
  const mercSouth = toMercator(tileToLat(y + 1, z));

  const columns = new Int32Array(TILE);
  for (let px = 0; px < TILE; px++) {
    let lon = west + ((px + 0.5) / TILE) * (east - west);
    while (lon < grid.lon0) lon += 360;
    while (lon >= grid.lon0 + 360) lon -= 360;
    const col = Math.floor((lon - grid.lon0) / grid.dh);
    columns[px] = col < grid.nx ? col : -1;
  }

  const image = ctx.createImageData(TILE, TILE);
  const data = image.data;
  let drawn = false;
  for (let py = 0; py < TILE; py++) {
    const lat = fromMercator(mercNorth - ((py + 0.5) / TILE) * (mercNorth - mercSouth));
    const row = Math.floor((lat - grid.lat0) / grid.dh);
    if (row < 0 || row >= grid.ny) continue;
    const base = row * grid.nx;
    for (let px = 0; px < TILE; px++) {
      const col = columns[px];
      if (col < 0) continue;
      const k = grid.lookup[base + col];
      if (k < 0 || s.hidden?.[k]) continue;
      const c = s.shade[k] * 3;
      const o = (py * TILE + px) * 4;
      data[o] = s.table[c];
      data[o + 1] = s.table[c + 1];
      data[o + 2] = s.table[c + 2];
      data[o + 3] = 255;
      drawn = true;
    }
  }
  if (drawn) ctx.putImageData(image, 0, 0);
}

function drawTile(canvas: HTMLCanvasElement, coords: L.Coords, style: TileStyle) {
  const n = 2 ** coords.z;
  if (coords.y < 0 || coords.y >= n) return;
  const x = ((coords.x % n) + n) % n;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  if (style.grid.type === 'quadtree') drawQuadtreeTile(ctx, coords.z, x, coords.y, style);
  else drawRegularTile(ctx, coords.z, x, coords.y, style);
}

export interface HoveredCell {
  index: number;
  lon: number;
  lat: number;
}

interface CellLayerProps {
  grid: CellGrid;
  /** Value of each cell, mapped onto `table` through `domain` (clamped). */
  values: ArrayLike<number>;
  /** 256-entry RGB lookup table (see rampTable). */
  table: Uint8ClampedArray;
  domain: [number, number];
  opacity: number;
  onHover?: (cell: HoveredCell | null) => void;
}

/**
 * Forecast or region cells as a Leaflet grid layer: tiles are drawn on demand at
 * every zoom level, so grids stay crisp and large (or multi-resolution) grids fast.
 */
export function CellLayer({ grid, values, table, domain, opacity, onHover }: CellLayerProps) {
  const map = useMap();
  const layerRef = useRef<L.GridLayer | null>(null);
  const styleRef = useRef<TileStyle | null>(null);
  const opacityRef = useRef(opacity);
  const onHoverRef = useRef(onHover);

  useEffect(() => {
    onHoverRef.current = onHover;
  }, [onHover]);

  const style = useMemo(() => buildStyle(grid, values, table, domain), [grid, values, table, domain]);

  useEffect(() => {
    const Layer = L.GridLayer.extend({
      createTile(coords: L.Coords) {
        const canvas = document.createElement('canvas');
        canvas.width = TILE;
        canvas.height = TILE;
        if (styleRef.current) drawTile(canvas, coords, styleRef.current);
        return canvas;
      },
    }) as unknown as new (options: L.GridLayerOptions) => L.GridLayer;
    const layer = new Layer({
      tileSize: TILE,
      className: 'raster-crisp',
      opacity: opacityRef.current,
      updateWhenZooming: false,
      keepBuffer: 1,
      zIndex: 5,
    });
    layer.addTo(map);
    layerRef.current = layer;
    return () => {
      layer.remove();
      layerRef.current = null;
    };
  }, [map]);

  useEffect(() => {
    styleRef.current = style;
    layerRef.current?.redraw();
  }, [style]);

  useEffect(() => {
    opacityRef.current = opacity;
    layerRef.current?.setOpacity(opacity);
  }, [opacity]);

  useEffect(() => {
    let frame = 0;
    const onMove = (event: L.LeafletMouseEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const { lng, lat } = event.latlng;
        const k = cellAt(grid, lng, lat);
        onHoverRef.current?.(k >= 0 ? { index: k, lon: lng, lat } : null);
      });
    };
    const onOut = () => {
      cancelAnimationFrame(frame);
      onHoverRef.current?.(null);
    };
    map.on('mousemove', onMove);
    map.on('mouseout', onOut);
    return () => {
      cancelAnimationFrame(frame);
      map.off('mousemove', onMove);
      map.off('mouseout', onOut);
    };
  }, [map, grid]);

  return null;
}
