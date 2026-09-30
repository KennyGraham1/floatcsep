'use client';

import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useMemo, useState } from 'react';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import { Select } from '@/components/ui/Select';
import { ErrorState, LoadingState, Skeleton } from '@/components/ui/States';
import { useForecast } from '@/lib/api';
import { forecastCells, regionGrid, type CellGrid } from '@/lib/grid';
import { modelGrid, splitModelName } from '@/lib/modelGrid';
import { formatInt } from '@/lib/format';
import type { Manifest } from '@/lib/types';

const MAP_HEIGHT = 380;

const RegionMap = dynamic(() => import('@/components/maps/RegionMap'), {
  ssr: false,
  loading: () => <Skeleton className="h-[380px] w-full rounded-lg" />,
});

function cellSizeKm(grid: CellGrid): string | null {
  if (grid.type !== 'quadtree') return null;
  // A tile at level L spans 40,075 km / 2^L at the equator.
  const size = (level: number) => Math.round(40075 / 2 ** level);
  const finest = grid.levels[grid.levels.length - 1];
  return `${formatInt(size(grid.levels[0]))} km to ${formatInt(size(finest))} km cells at the equator`;
}

/** The testing region, or the forecasts' own (e.g. quadtree) grids when there is none. */
export function GridCard({ manifest, className }: { manifest: Manifest; className?: string }) {
  const region = manifest.region;
  const fixedGrid = useMemo(() => regionGrid(region), [region]);
  // Grids of forecast files; forecasts of every cell of a regular grid (external,
  // e.g. the models' native grid) are too large to draw as a grid, and are listed below.
  const dimension = useMemo(() => modelGrid(manifest.models.filter((m) => !m.external)), [manifest.models]);
  const otherGrids = useMemo(() => {
    const shown = new Set(dimension?.grids ?? []);
    const others = new Map<string, { model: string | null; cells: number | null; dh: number | null }>();
    for (const m of manifest.models) {
      const grid = splitModelName(m.name).grid;
      if (m.external && grid && !shown.has(grid) && !others.has(grid)) {
        others.set(grid, { model: m.name, cells: m.external.grid.nx * m.external.grid.ny, dh: m.external.grid.dh });
      }
    }
    for (const e of manifest.evaluations) {
      const grid = splitModelName(e.model).grid;
      if (grid && !shown.has(grid) && !others.has(grid)) others.set(grid, { model: null, cells: null, dh: null });
    }
    return [...others.entries()];
  }, [manifest.models, manifest.evaluations, dimension]);
  const [gridName, setGridName] = useState(() => dimension?.grids[0] ?? null);

  // Without a fixed region, show the grid of a forecast (the first model on the grid).
  const source = useMemo(() => {
    if (fixedGrid) return null;
    const candidates = manifest.models
      .map((model, index) => ({ model, index }))
      .filter(({ model }) => !dimension || splitModelName(model.name).grid === gridName);
    for (const { model, index } of candidates) {
      const window = model.forecast_available.findIndex(Boolean);
      if (window >= 0) return { model: index, window };
    }
    return null;
  }, [fixedGrid, manifest.models, dimension, gridName]);

  const { data, error, isLoading } = useForecast(source?.model ?? null, source?.window ?? null);
  const forecastGrid = useMemo(() => (data && !fixedGrid ? forecastCells(data).grid : null), [data, fixedGrid]);
  const grid = fixedGrid ?? forecastGrid;
  const label = fixedGrid
    ? (region?.name ?? 'Testing region')
    : dimension && gridName
      ? gridName
      : data?.grid === 'quadtree'
        ? 'Quadtree grid'
        : 'Forecast grid';

  const title = fixedGrid ? 'Testing region' : dimension ? 'Forecast grids' : 'Forecast grid';
  const description = fixedGrid
    ? region?.name
      ? `Grid cells of ${region.name}`
      : 'Grid cells where forecasts are evaluated'
    : grid?.type === 'quadtree'
      ? `Multi-resolution quadtree cells, shaded by zoom level${dimension ? ` · ${dimension.grids.length} grids` : ''}`
      : 'Cells of the forecasts (the experiment has no fixed region)';

  let body;
  if (grid) {
    body = <RegionMap grid={grid} label={label} height={MAP_HEIGHT} />;
  } else if (error) {
    body = <ErrorState title="The grid could not be loaded" message={error.message} details={error.details} />;
  } else if (isLoading) {
    body = <LoadingState title="Loading the grid…" className="h-[380px]" />;
  } else {
    body = <p className="px-2 py-10 text-center text-xs text-ink-3">This experiment has no spatial grid to show.</p>;
  }

  const extent = grid ? cellSizeKm(grid) : null;

  return (
    <Card className={className}>
      <CardHeader
        title={title}
        description={description}
        actions={
          dimension &&
          !fixedGrid && (
            <Select
              label="Grid"
              hideLabel
              className="w-40"
              value={gridName ?? ''}
              onChange={setGridName}
              options={dimension.grids.map((g) => ({ value: g, label: g }))}
            />
          )
        }
      />
      <CardBody className="p-3">
        <ErrorBoundary label="The grid map">{body}</ErrorBoundary>
        {grid?.type === 'quadtree' && (
          <p className="mt-2.5 px-1 text-xs text-ink-3">
            {formatInt(grid.n)} cells · zoom levels {grid.levels[0]}–{grid.levels[grid.levels.length - 1]}
            {extent ? ` · ${extent}` : ''}
          </p>
        )}
        {otherGrids.map(([name, other]) => (
          <p key={name} className="mt-1.5 px-1 text-xs text-ink-3">
            Also tested on <span className="font-medium text-ink-2">{name}</span>
            {other.cells !== null && other.dh !== null
              ? `, a regular ${other.dh}° grid of ${formatInt(other.cells)} cells`
              : ''}
            {' · '}
            {other.model && (
              <>
                <Link href={`/forecasts?model=${encodeURIComponent(other.model)}`} className="link">
                  forecasts
                </Link>
                {' · '}
              </>
            )}
            <Link href={`/results?grid=${encodeURIComponent(name)}`} className="link">
              results
            </Link>
          </p>
        ))}
      </CardBody>
    </Card>
  );
}
