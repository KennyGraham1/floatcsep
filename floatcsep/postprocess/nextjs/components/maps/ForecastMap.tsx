'use client';

import { useCallback, useMemo, useState } from 'react';
import { useThemeMode } from '@/hooks/useThemeMode';
import type { Catalog } from '@/lib/catalog';
import { CHROME, EVENT_COLORS, HEAT, rampGradient, rampTable } from '@/lib/colors';
import { formatLatLon, formatSci } from '@/lib/format';
import { eventTooltip } from './CatalogMap';
import { EventsLayer } from './EventsLayer';
import MapView from './MapView';
import { ColorScaleLegend, LegendDot, MapPanel } from './MapOverlays';
import { gridBounds, RasterLayer, type GridRaster, type HoveredCell } from './RasterLayer';

interface ForecastMapProps {
  grid: GridRaster & { rates: Float64Array };
  /** Colour range in log10 units. */
  range: [number, number];
  opacity: number;
  observed: { catalog: Catalog; indices: Uint32Array } | null;
  /** Pixel height; fills the parent when omitted. */
  height?: number;
}

export default function ForecastMap({ grid, range, opacity, observed, height }: ForecastMapProps) {
  const mode = useThemeMode();
  const table = useMemo(() => rampTable(HEAT[mode]), [mode]);
  const bounds = useMemo(() => gridBounds(grid), [grid]);
  const [hover, setHover] = useState<HoveredCell | null>(null);
  const observedColor = EVENT_COLORS[mode].input;

  const colorFor = useCallback(() => observedColor, [observedColor]);
  const radiusFor = useCallback(() => 5, []);
  const tooltip = useCallback((i: number) => (observed ? eventTooltip(observed.catalog, i) : ''), [observed]);

  return (
    <MapView
      bounds={bounds}
      fitKey={`${grid.lon0}:${grid.lat0}:${grid.nx}:${grid.ny}:${grid.dh}`}
      height={height}
      ariaLabel="Map of forecast rates per cell"
      labelsOnTop
      overlays={
        <>
          {hover && (
            <MapPanel position="top-left" live>
              <div className="font-medium tabular">λ = {formatSci(grid.rates[hover.index])}</div>
              <div className="tabular text-ink-3">{formatLatLon(hover.lat, hover.lon)}</div>
            </MapPanel>
          )}
          <MapPanel position="bottom-left">
            <ColorScaleLegend
              title={
                <>
                  Expected events per cell (log<sub>10</sub> λ)
                </>
              }
              gradient={rampGradient(HEAT[mode])}
              min={`≤ ${range[0].toFixed(1)}`}
              max={`≥ ${range[1].toFixed(1)}`}
            />
            {observed && (
              <div className="mt-2 flex items-center gap-2 border-t pt-2">
                <LegendDot color={observedColor} />
                <span>Observed events</span>
                <span className="ml-auto pl-3 tabular text-ink-3">{observed.indices.length}</span>
              </div>
            )}
          </MapPanel>
        </>
      }
    >
      <RasterLayer grid={grid} table={table} domain={range} opacity={opacity} onHover={setHover} />
      {observed && (
        <EventsLayer
          catalog={observed.catalog}
          indices={observed.indices}
          colorFor={colorFor}
          radiusFor={radiusFor}
          ring={CHROME[mode].surface}
          tooltip={tooltip}
          unwrap={grid.lon0 + grid.nx * grid.dh > 180}
          fillOpacity={0.95}
        />
      )}
    </MapView>
  );
}
