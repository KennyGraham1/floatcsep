'use client';

import L from 'leaflet';
import { useCallback, useMemo, useState, type ReactNode } from 'react';
import { useThemeMode } from '@/hooks/useThemeMode';
import type { Catalog } from '@/lib/catalog';
import { CHROME, EVENT_COLORS, rampGradient, rampTable } from '@/lib/colors';
import { formatLatLon, formatSci } from '@/lib/format';
import { gridExtent, viewExtent, type ForecastCells } from '@/lib/grid';
import { CellLayer, type HoveredCell } from './CellLayer';
import { eventTooltip } from './CatalogMap';
import { EventsLayer } from './EventsLayer';
import MapView from './MapView';
import { ColorScaleLegend, LegendDot, MapPanel } from './MapOverlays';

/** Rate densities are shown per this area, in km². */
export const DENSITY_AREA = 10_000;

interface ForecastMapProps {
  cells: ForecastCells;
  /** log10 of the displayed measure, per cell. */
  values: Float64Array;
  measure: 'rate' | 'density';
  /** Colour range in log10 units. */
  range: [number, number];
  /** Colour palette stops, low → high. */
  stops: string[];
  opacity: number;
  observed: { catalog: Catalog; indices: Uint32Array } | null;
  height?: number;
}

export default function ForecastMap({
  cells,
  values,
  measure,
  range,
  stops,
  opacity,
  observed,
  height,
}: ForecastMapProps) {
  const mode = useThemeMode();
  const table = useMemo(() => rampTable(stops), [stops]);
  const { grid } = cells;
  const extent = useMemo(() => viewExtent(gridExtent(grid)), [grid]);
  const bounds = useMemo(() => L.latLngBounds([extent[0], extent[1]], [extent[2], extent[3]]), [extent]);
  const [hover, setHover] = useState<HoveredCell | null>(null);
  const observedColor = EVENT_COLORS[mode].input;
  // Events are drawn in the longitude frame of the view: past 180° for grids that
  // cross the antimeridian and for global grids, which are shown Pacific-centred.
  const unwrap = extent[3] > 180;

  const colorFor = useCallback(() => observedColor, [observedColor]);
  const radiusFor = useCallback(() => 5, []);
  const tooltip = useCallback((i: number) => (observed ? eventTooltip(observed.catalog, i) : ''), [observed]);

  let readout: ReactNode = null;
  if (hover) {
    const k = hover.index;
    const rate = cells.rates[k];
    const density = (rate / cells.areas[k]) * DENSITY_AREA;
    readout = (
      <>
        <div className="font-medium tabular">
          {measure === 'density' ? `${formatSci(density)} per 10⁴ km²` : `λ = ${formatSci(rate)}`}
        </div>
        <div className="tabular text-ink-3">
          {measure === 'density' ? `λ = ${formatSci(rate)} in the cell` : `${formatSci(density)} per 10⁴ km²`}
        </div>
        {grid.type === 'quadtree' && (
          <div className="tabular text-ink-3">
            Level {grid.quadkeys[k].length} · {Math.round(cells.areas[k]).toLocaleString('en-US')} km²
          </div>
        )}
        <div className="tabular text-ink-3">{formatLatLon(hover.lat, hover.lon)}</div>
      </>
    );
  }

  return (
    <MapView
      bounds={bounds}
      fitKey={`${grid.type}:${grid.n}:${extent.join(',')}`}
      height={height}
      ariaLabel="Map of forecast rates per cell"
      labelsOnTop
      overlays={
        <>
          {readout && (
            <MapPanel position="top-left" live>
              {readout}
            </MapPanel>
          )}
          <MapPanel position="bottom-left">
            <ColorScaleLegend
              title={
                measure === 'density' ? (
                  <>
                    Expected events per 10⁴ km² (log<sub>10</sub>)
                  </>
                ) : (
                  <>
                    Expected events per cell (log<sub>10</sub> λ)
                  </>
                )
              }
              gradient={rampGradient(stops)}
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
      <CellLayer grid={grid} values={values} table={table} domain={range} opacity={opacity} onHover={setHover} />
      {observed && (
        <EventsLayer
          catalog={observed.catalog}
          indices={observed.indices}
          colorFor={colorFor}
          radiusFor={radiusFor}
          ring={CHROME[mode].surface}
          tooltip={tooltip}
          unwrap={unwrap}
          fillOpacity={0.95}
        />
      )}
    </MapView>
  );
}
