'use client';

import L from 'leaflet';
import { useMemo, useState } from 'react';
import { useThemeMode } from '@/hooks/useThemeMode';
import { HEAT, REGION_FILL, rampGradient, rampTable } from '@/lib/colors';
import { formatInt, formatLatLon } from '@/lib/format';
import { gridExtent, solidTable, type CellGrid } from '@/lib/grid';
import { CellLayer, type HoveredCell } from './CellLayer';
import MapView from './MapView';
import { ColorScaleLegend, LegendDot, MapPanel } from './MapOverlays';

interface RegionMapProps {
  grid: CellGrid;
  /** Region or grid name for the legend. */
  label: string;
  height: number;
}

/**
 * The cells of a testing region or forecast grid. Quadtree grids are shaded by
 * zoom level, so their multi-resolution structure is visible.
 */
export default function RegionMap({ grid, label, height }: RegionMapProps) {
  const mode = useThemeMode();
  const extent = useMemo(() => gridExtent(grid), [grid]);
  const bounds = useMemo(() => L.latLngBounds([extent[0], extent[1]], [extent[2], extent[3]]), [extent]);
  const [hover, setHover] = useState<HoveredCell | null>(null);

  const levels = useMemo(() => {
    if (grid.type !== 'quadtree') return null;
    return {
      values: Float64Array.from(grid.quadkeys, (q) => q.length),
      min: grid.levels[0],
      max: grid.levels[grid.levels.length - 1],
    };
  }, [grid]);
  const values = useMemo(() => levels?.values ?? new Float64Array(grid.n).fill(1), [levels, grid.n]);
  const table = useMemo(() => (levels ? rampTable(HEAT[mode]) : solidTable(REGION_FILL[mode])), [levels, mode]);
  const domain = useMemo<[number, number]>(
    () => (levels ? [levels.min, Math.max(levels.max, levels.min + 1)] : [0, 1]),
    [levels],
  );

  return (
    <MapView
      bounds={bounds}
      fitKey={`${label}:${grid.type}:${grid.n}`}
      height={height}
      ariaLabel={`Map of the cells of ${label}`}
      labelsOnTop
      overlays={
        <>
          {hover && (
            <MapPanel position="top-left" live>
              {grid.type === 'quadtree' ? (
                <>
                  <div className="font-medium tabular">Level {grid.quadkeys[hover.index].length}</div>
                  <div className="font-mono text-2xs text-ink-3">{grid.quadkeys[hover.index]}</div>
                </>
              ) : (
                <div className="font-medium">Cell</div>
              )}
              <div className="tabular text-ink-3">{formatLatLon(hover.lat, hover.lon)}</div>
            </MapPanel>
          )}
          <MapPanel position="bottom-left">
            {levels ? (
              <ColorScaleLegend
                title={`${label} · ${formatInt(grid.n)} cells · zoom level`}
                gradient={rampGradient(HEAT[mode])}
                min={`${levels.min} (coarse)`}
                max={`${levels.max} (fine)`}
              />
            ) : (
              <div className="flex items-center gap-2">
                <LegendDot color={REGION_FILL[mode]} />
                <span className="font-medium">{label}</span>
                <span className="tabular text-ink-3">
                  {formatInt(grid.n)} cells{grid.type === 'regular' ? ` · ${grid.dh}°` : ''}
                </span>
              </div>
            )}
          </MapPanel>
        </>
      }
    >
      <CellLayer
        grid={grid}
        values={values}
        table={table}
        domain={domain}
        opacity={levels ? 0.6 : 0.4}
        onHover={setHover}
      />
    </MapView>
  );
}
