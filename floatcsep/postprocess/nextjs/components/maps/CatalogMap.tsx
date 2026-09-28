'use client';

import L from 'leaflet';
import { useCallback, useMemo } from 'react';
import { useThemeMode } from '@/hooks/useThemeMode';
import { INPUT, type Catalog } from '@/lib/catalog';
import { CHROME, EVENT_COLORS } from '@/lib/colors';
import { formatInt, formatLatLon, formatMagnitude } from '@/lib/format';
import { formatDateTime } from '@/lib/time';
import { escapeHtml } from '@/lib/utils';
import { EventsLayer, magnitudeRadius, needsUnwrap } from './EventsLayer';
import MapView from './MapView';
import { LegendDot, MapPanel } from './MapOverlays';

interface CatalogMapProps {
  catalog: Catalog;
  indices: Uint32Array;
  height: number;
  /** Bounds to show when no event passes the filter. */
  fallbackBounds: [number, number, number, number] | null;
}

export function eventTooltip(catalog: Catalog, i: number): string {
  const depth = catalog.depth[i];
  return [
    `<div style="font-weight:600">M ${formatMagnitude(catalog.mag[i])} <span style="font-weight:400;opacity:.7">· ${escapeHtml(catalog.id[i])}</span></div>`,
    `<div>${escapeHtml(formatDateTime(catalog.time[i]))} UTC</div>`,
    `<div style="opacity:.75">${escapeHtml(formatLatLon(catalog.lat[i], catalog.lon[i]))}${
      Number.isFinite(depth) ? ` · ${depth.toFixed(1)} km` : ''
    }</div>`,
  ].join('');
}

export default function CatalogMap({ catalog, indices, height, fallbackBounds }: CatalogMapProps) {
  const mode = useThemeMode();
  const colors = EVENT_COLORS[mode];

  const summary = useMemo(() => {
    let input = 0;
    let minMag = Infinity;
    let maxMag = -Infinity;
    const lons = new Float64Array(indices.length);
    indices.forEach((i, j) => {
      if (catalog.kind[i] === INPUT) input++;
      if (catalog.mag[i] < minMag) minMag = catalog.mag[i];
      if (catalog.mag[i] > maxMag) maxMag = catalog.mag[i];
      lons[j] = catalog.lon[i];
    });
    return { input, test: indices.length - input, minMag, maxMag, unwrap: needsUnwrap(lons) };
  }, [catalog, indices]);

  const bounds = useMemo(() => {
    if (indices.length === 0) {
      if (!fallbackBounds) return null;
      const [w, s, e, n] = fallbackBounds;
      return L.latLngBounds([s, w], [n, e]);
    }
    let s = Infinity;
    let n = -Infinity;
    let w = Infinity;
    let e = -Infinity;
    for (const i of indices) {
      const lon = summary.unwrap && catalog.lon[i] < 0 ? catalog.lon[i] + 360 : catalog.lon[i];
      s = Math.min(s, catalog.lat[i]);
      n = Math.max(n, catalog.lat[i]);
      w = Math.min(w, lon);
      e = Math.max(e, lon);
    }
    return L.latLngBounds([s, w], [n, e]).pad(0.02);
  }, [catalog, indices, summary.unwrap, fallbackBounds]);

  const radiusFor = useMemo(
    () => magnitudeRadius(Number.isFinite(summary.minMag) ? summary.minMag : 0),
    [summary.minMag],
  );
  const colorFor = useCallback(
    (i: number) => (catalog.kind[i] === INPUT ? colors.input : colors.test),
    [catalog, colors],
  );
  const tooltip = useCallback((i: number) => eventTooltip(catalog, i), [catalog]);

  const sizeSteps = useMemo(() => {
    if (!Number.isFinite(summary.minMag)) return [];
    const lo = Math.ceil(summary.minMag);
    const hi = Math.floor(summary.maxMag);
    const steps = hi - lo >= 2 ? [lo, Math.round((lo + hi) / 2), hi] : hi > lo ? [lo, hi] : [lo];
    return steps.filter((m) => m >= summary.minMag - 1e-9);
  }, [summary.minMag, summary.maxMag]);

  return (
    <MapView
      bounds={bounds}
      fitKey={bounds ? bounds.toBBoxString() : 'none'}
      height={height}
      ariaLabel={`Map of ${indices.length} catalog events`}
      overlays={
        <MapPanel position="bottom-left">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <LegendDot color={colors.input} />
              <span>Before start</span>
              <span className="ml-auto pl-3 tabular text-ink-3">{formatInt(summary.input)}</span>
            </div>
            <div className="flex items-center gap-2">
              <LegendDot color={colors.test} />
              <span>Experiment period</span>
              <span className="ml-auto pl-3 tabular text-ink-3">{formatInt(summary.test)}</span>
            </div>
          </div>
          {sizeSteps.length > 0 && (
            <div className="mt-2 flex items-end gap-3 border-t pt-2">
              {sizeSteps.map((m) => {
                const r = radiusFor(m);
                return (
                  <span key={m} className="flex flex-col items-center gap-1">
                    <span
                      className="rounded-full border border-ink-3"
                      style={{ width: r * 2, height: r * 2 }}
                      aria-hidden
                    />
                    <span className="tabular text-2xs text-ink-3">M{m}</span>
                  </span>
                );
              })}
            </div>
          )}
        </MapPanel>
      }
    >
      <EventsLayer
        catalog={catalog}
        indices={indices}
        colorFor={colorFor}
        radiusFor={radiusFor}
        ring={CHROME[mode].surface}
        tooltip={tooltip}
        unwrap={summary.unwrap}
      />
    </MapView>
  );
}
