'use client';

import L from 'leaflet';
import { useEffect, useMemo, useRef } from 'react';
import { useMap } from 'react-leaflet';
import type { Catalog } from '@/lib/catalog';

interface EventsLayerProps {
  catalog: Catalog;
  indices: Uint32Array;
  colorFor: (index: number) => string;
  radiusFor: (magnitude: number) => number;
  /** Ring colour separating overlapping markers (the map surface). */
  ring: string;
  /** HTML (already escaped) shown when hovering an event. */
  tooltip: (index: number) => string;
  /** Add 360° to western longitudes, for data around the antimeridian. */
  unwrap?: boolean;
  fillOpacity?: number;
}

const BUCKET = 24;

/**
 * Catalog events as canvas circle markers. Hover uses a screen-space grid index
 * to find the nearest event, so large catalogs stay responsive.
 */
export function EventsLayer({
  catalog,
  indices,
  colorFor,
  radiusFor,
  ring,
  tooltip,
  unwrap = false,
  fillOpacity = 0.8,
}: EventsLayerProps) {
  const map = useMap();
  const renderer = useMemo(() => L.canvas({ padding: 0.3 }), []);
  const tooltipRef = useRef(tooltip);

  useEffect(() => {
    tooltipRef.current = tooltip;
  }, [tooltip]);

  // Largest first, so smaller events stay visible on top.
  const order = useMemo(() => Array.from(indices).sort((a, b) => catalog.mag[b] - catalog.mag[a]), [catalog, indices]);
  const lonOf = useMemo(
    () => (i: number) => (unwrap && catalog.lon[i] < 0 ? catalog.lon[i] + 360 : catalog.lon[i]),
    [catalog, unwrap],
  );

  useEffect(() => {
    const group = L.layerGroup();
    for (const i of order) {
      L.circleMarker([catalog.lat[i], lonOf(i)], {
        renderer,
        radius: radiusFor(catalog.mag[i]),
        color: ring,
        weight: 1,
        fillColor: colorFor(i),
        fillOpacity,
        interactive: false,
      }).addTo(group);
    }
    group.addTo(map);
    return () => {
      group.remove();
    };
  }, [map, renderer, catalog, order, lonOf, colorFor, radiusFor, ring, fillOpacity]);

  useEffect(() => {
    let xs = new Float32Array(0);
    let ys = new Float32Array(0);
    let ids = new Uint32Array(0);
    let buckets = new Map<number, number[]>();

    const reindex = () => {
      const size = map.getSize();
      const n = order.length;
      xs = new Float32Array(n);
      ys = new Float32Array(n);
      ids = new Uint32Array(n);
      buckets = new Map();
      let m = 0;
      for (const i of order) {
        const p = map.latLngToContainerPoint([catalog.lat[i], lonOf(i)]);
        if (p.x < -BUCKET || p.y < -BUCKET || p.x > size.x + BUCKET || p.y > size.y + BUCKET) continue;
        xs[m] = p.x;
        ys[m] = p.y;
        ids[m] = i;
        const key = Math.floor(p.x / BUCKET) * 100_000 + Math.floor(p.y / BUCKET);
        const bucket = buckets.get(key);
        if (bucket) bucket.push(m);
        else buckets.set(key, [m]);
        m++;
      }
    };

    const highlight = L.circleMarker([0, 0], {
      renderer,
      radius: 6,
      color: ring,
      weight: 2.5,
      fill: false,
      interactive: false,
    });
    const tip = L.tooltip({ direction: 'top', offset: [0, -6], className: 'map-tooltip', opacity: 1 });
    let shown = -1;

    const hide = () => {
      if (shown < 0) return;
      shown = -1;
      highlight.remove();
      map.closeTooltip(tip);
    };

    let frame = 0;
    const onMove = (event: L.LeafletMouseEvent) => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const { x, y } = event.containerPoint;
        const bx = Math.floor(x / BUCKET);
        const by = Math.floor(y / BUCKET);
        let best = -1;
        let bestDistance = Infinity;
        for (let dx = -1; dx <= 1; dx++) {
          for (let dy = -1; dy <= 1; dy++) {
            for (const m of buckets.get((bx + dx) * 100_000 + (by + dy)) ?? []) {
              const d = (xs[m] - x) ** 2 + (ys[m] - y) ** 2;
              const reach = Math.max(9, radiusFor(catalog.mag[ids[m]]) + 3);
              if (d < bestDistance && d <= reach * reach) {
                best = m;
                bestDistance = d;
              }
            }
          }
        }
        if (best < 0) {
          hide();
          return;
        }
        const i = ids[best];
        if (i === shown) return;
        shown = i;
        const latlng = L.latLng(catalog.lat[i], lonOf(i));
        highlight
          .setLatLng(latlng)
          .setRadius(radiusFor(catalog.mag[i]) + 2)
          .addTo(map);
        tip.setLatLng(latlng).setContent(tooltipRef.current(i));
        map.openTooltip(tip);
      });
    };

    reindex();
    map.on('moveend zoomend resize viewreset', reindex);
    map.on('mousemove', onMove);
    map.on('mouseout movestart zoomstart', hide);
    return () => {
      cancelAnimationFrame(frame);
      map.off('moveend zoomend resize viewreset', reindex);
      map.off('mousemove', onMove);
      map.off('mouseout movestart zoomstart', hide);
      hide();
    };
  }, [map, renderer, catalog, order, lonOf, radiusFor, ring]);

  return null;
}

/** Marker radius in pixels, growing with magnitude above the smallest shown. */
export function magnitudeRadius(minMagnitude: number) {
  return (magnitude: number) => Math.min(16, 2.5 + Math.max(0, magnitude - minMagnitude) * 2.1);
}

/**
 * Whether longitudes should be unwrapped to keep data near 180° contiguous: only
 * when that clearly shortens their span, so global data keep the usual frame.
 */
export function needsUnwrap(lons: ArrayLike<number>): boolean {
  let min = Infinity;
  let max = -Infinity;
  let minShifted = Infinity;
  let maxShifted = -Infinity;
  for (let i = 0; i < lons.length; i++) {
    const lon = lons[i];
    const shifted = lon < 0 ? lon + 360 : lon;
    if (lon < min) min = lon;
    if (lon > max) max = lon;
    if (shifted < minShifted) minShifted = shifted;
    if (shifted > maxShifted) maxShifted = shifted;
  }
  return max - min > 180 && maxShifted - minShifted < max - min - 45;
}
