'use client';

import { useMemo, useState } from 'react';
import { useThemeMode } from '@/hooks/useThemeMode';
import { REGION_FILL } from '@/lib/colors';
import { formatInt, formatLatLon } from '@/lib/format';
import { regionRaster, solidTable } from '@/lib/grid';
import type { Region } from '@/lib/types';
import MapView from './MapView';
import { LegendDot, MapPanel } from './MapOverlays';
import { gridBounds, RasterLayer, type HoveredCell } from './RasterLayer';

export default function RegionMap({ region, height }: { region: Region; height: number }) {
  const mode = useThemeMode();
  const grid = useMemo(() => regionRaster(region), [region]);
  const table = useMemo(() => solidTable(REGION_FILL[mode]), [mode]);
  const bounds = useMemo(() => (grid ? gridBounds(grid) : null), [grid]);
  const [hover, setHover] = useState<HoveredCell | null>(null);
  const domain = useMemo<[number, number]>(() => [0, 1], []);

  return (
    <MapView
      bounds={bounds}
      fitKey={`${region.name}:${grid?.nx}:${grid?.ny}`}
      height={height}
      ariaLabel="Map of the experiment's testing region"
      labelsOnTop
      overlays={
        <>
          {hover && grid && (
            <MapPanel position="top-left" live>
              <span className="tabular">{formatLatLon(hover.lat, hover.lon)}</span>
              <span className="text-ink-3"> · cell centre</span>
            </MapPanel>
          )}
          <MapPanel position="bottom-left">
            <div className="flex items-center gap-2">
              <LegendDot color={REGION_FILL[mode]} />
              <span className="font-medium">Testing region</span>
              {grid && (
                <span className="tabular text-ink-3">
                  {formatInt(grid.ix.length)} cells · {region.dh}°
                </span>
              )}
            </div>
          </MapPanel>
        </>
      }
    >
      {grid && <RasterLayer grid={grid} table={table} domain={domain} opacity={0.4} onHover={setHover} />}
    </MapView>
  );
}
