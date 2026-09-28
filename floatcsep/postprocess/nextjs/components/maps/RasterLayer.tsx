'use client';

import L from 'leaflet';
import { useEffect, useMemo, useRef } from 'react';
import { useMap } from 'react-leaflet';

/** Cells on a regular lon/lat grid, addressed by integer column/row. */
export interface GridRaster {
  lon0: number;
  lat0: number;
  dh: number;
  nx: number;
  ny: number;
  ix: ArrayLike<number>;
  iy: ArrayLike<number>;
  values: ArrayLike<number>;
}

export interface HoveredCell {
  /** Cell centre. */
  lon: number;
  lat: number;
  value: number;
  index: number;
}

export function gridBounds(grid: GridRaster): L.LatLngBounds {
  return L.latLngBounds([grid.lat0, grid.lon0], [grid.lat0 + grid.ny * grid.dh, grid.lon0 + grid.nx * grid.dh]);
}

const MAX_LAT = 85.05112878;
const toMercator = (lat: number) => {
  const r = (Math.min(MAX_LAT, Math.max(-MAX_LAT, lat)) * Math.PI) / 180;
  return Math.log(Math.tan(Math.PI / 4 + r / 2));
};
const fromMercator = (y: number) => ((2 * Math.atan(Math.exp(y)) - Math.PI / 2) * 180) / Math.PI;

interface RasterLayerProps {
  grid: GridRaster;
  /** 256-entry RGB lookup table (see rampTable). */
  table: Uint8ClampedArray;
  /** Values mapped to the ends of the table; outside values are clamped. */
  domain: [number, number];
  opacity: number;
  onHover?: (cell: HoveredCell | null) => void;
}

/**
 * Draws the grid as one image overlay: one pixel column per grid column, rows
 * resampled along Web Mercator so every cell lands exactly on its latitude band.
 * Scales to millions of cells, unlike one vector shape per cell.
 */
export function RasterLayer({ grid, table, domain, opacity, onHover }: RasterLayerProps) {
  const map = useMap();
  const current = useRef<{ overlay: L.ImageOverlay; url: string } | null>(null);
  const opacityRef = useRef(opacity);
  const onHoverRef = useRef(onHover);

  useEffect(() => {
    onHoverRef.current = onHover;
  }, [onHover]);

  const lookup = useMemo(() => {
    const index = new Int32Array(grid.nx * grid.ny).fill(-1);
    for (let k = 0; k < grid.ix.length; k++) index[grid.iy[k] * grid.nx + grid.ix[k]] = k;
    return index;
  }, [grid]);

  useEffect(() => {
    const { lon0, lat0, dh, nx, ny, ix, iy, values } = grid;
    const [vmin, vmax] = domain;
    const span = vmax - vmin || 1;

    // Colour every grid cell once (row 0 = southernmost row).
    const cells = new Uint8ClampedArray(nx * ny * 4);
    for (let k = 0; k < values.length; k++) {
      const t = Math.min(1, Math.max(0, (values[k] - vmin) / span));
      const c = Math.round(t * 255) * 3;
      const p = (iy[k] * nx + ix[k]) * 4;
      cells[p] = table[c];
      cells[p + 1] = table[c + 1];
      cells[p + 2] = table[c + 2];
      cells[p + 3] = 255;
    }

    const south = lat0;
    const north = lat0 + ny * dh;
    const yNorth = toMercator(north);
    const ySouth = toMercator(south);
    const height = Math.min(4096, Math.max(256, ny * 8));
    const canvas = document.createElement('canvas');
    canvas.width = nx;
    canvas.height = height;
    const context = canvas.getContext('2d');
    if (!context) return;
    const image = context.createImageData(nx, height);
    for (let r = 0; r < height; r++) {
      const lat = fromMercator(yNorth + ((r + 0.5) / height) * (ySouth - yNorth));
      const row = Math.floor((lat - lat0) / dh);
      if (row < 0 || row >= ny) continue;
      image.data.set(cells.subarray(row * nx * 4, (row + 1) * nx * 4), r * nx * 4);
    }
    context.putImageData(image, 0, 0);

    let cancelled = false;
    let pending: { overlay: L.ImageOverlay; url: string } | null = null;
    canvas.toBlob((blob) => {
      if (cancelled || !blob) return;
      const url = URL.createObjectURL(blob);
      const overlay = L.imageOverlay(url, L.latLngBounds([south, lon0], [north, lon0 + nx * dh]), {
        opacity: opacityRef.current,
        className: 'raster-crisp',
        interactive: false,
      });
      pending = { overlay, url };
      // Swap only once the new image is decoded, so recolouring never flickers.
      overlay.once('load', () => {
        const previous = current.current;
        current.current = { overlay, url };
        pending = null;
        if (previous) {
          previous.overlay.remove();
          URL.revokeObjectURL(previous.url);
        }
      });
      overlay.addTo(map);
    });

    return () => {
      cancelled = true;
      if (pending) {
        pending.overlay.remove();
        URL.revokeObjectURL(pending.url);
      }
    };
  }, [map, grid, table, domain]);

  useEffect(() => {
    opacityRef.current = opacity;
    current.current?.overlay.setOpacity(opacity);
  }, [opacity]);

  useEffect(
    () => () => {
      if (current.current) {
        current.current.overlay.remove();
        URL.revokeObjectURL(current.current.url);
        current.current = null;
      }
    },
    [map],
  );

  useEffect(() => {
    let frame = 0;
    const onMove = (event: L.LeafletMouseEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const { lon0, lat0, dh, nx, ny } = grid;
        let lon = event.latlng.lng;
        while (lon < lon0) lon += 360;
        while (lon >= lon0 + 360) lon -= 360;
        const col = Math.floor((lon - lon0) / dh);
        const row = Math.floor((event.latlng.lat - lat0) / dh);
        const k = col >= 0 && col < nx && row >= 0 && row < ny ? lookup[row * nx + col] : -1;
        onHoverRef.current?.(
          k >= 0 ? { lon: lon0 + (col + 0.5) * dh, lat: lat0 + (row + 0.5) * dh, value: grid.values[k], index: k } : null,
        );
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
  }, [map, grid, lookup]);

  return null;
}
