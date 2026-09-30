'use client';

import { ChevronLeft, ChevronRight, FileX2, RotateCcw } from 'lucide-react';
import dynamic from 'next/dynamic';
import { Suspense, useEffect, useMemo, useState, type ReactNode } from 'react';
import { ChartCard } from '@/components/charts/ChartCard';
import MagnitudeRateChart from '@/components/charts/MagnitudeRateChart';
import RateHistogram from '@/components/charts/RateHistogram';
import { FilterBar, PageHeader } from '@/components/layout/PageHeader';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import { PalettePicker } from '@/components/ui/PalettePicker';
import { RangeSlider } from '@/components/ui/RangeSlider';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Select } from '@/components/ui/Select';
import { Slider } from '@/components/ui/Slider';
import { StatGrid, StatTile } from '@/components/ui/StatTile';
import { EmptyState, ErrorState, LoadingState, Skeleton } from '@/components/ui/States';
import { Switch } from '@/components/ui/Switch';
import { useElapsed } from '@/hooks/useElapsed';
import { useObservedCatalog } from '@/hooks/useObservedCatalog';
import { indexByName, useQueryState, windowIndexFromParam } from '@/hooks/useQueryState';
import { usePersistentState } from '@/hooks/usePersistentState';
import { useThemeMode } from '@/hooks/useThemeMode';
import { prefetchForecast, useForecast } from '@/lib/api';
import { eventsInWindow, regionMask } from '@/lib/catalog';
import { PALETTE_NAMES, paletteStops, rampGradient, type PaletteName } from '@/lib/colors';
import { useLoadedManifest } from '@/lib/contexts/ManifestContext';
import { formatInt, formatLatLon, formatRate, formatSci, magnitudeBinLabel, magnitudeDecimals } from '@/lib/format';
import { cellBounds, forecastCells } from '@/lib/grid';
import { gridLabel, modelGrid, regularGridSizes, splitModelName } from '@/lib/modelGrid';
import { formatDate, formatDuration, parseTimeWindows } from '@/lib/time';
import { clamp, cn } from '@/lib/utils';

const ForecastMap = dynamic(() => import('@/components/maps/ForecastMap'), {
  ssr: false,
  loading: () => <Skeleton className="h-full min-h-[536px] w-full rounded-lg" />,
});

export default function ForecastsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-xl" />}>
      <ForecastsView />
    </Suspense>
  );
}

/** Rate densities are shown per this area, in km² (see ForecastMap). */
const DENSITY_AREA = 10_000;

type Measure = 'rate' | 'density';

/** Colour-scale domain (log10, rounded to 0.1) around the displayed values. */
function valueDomain(values: Float64Array): [number, number] {
  let min = Infinity;
  let max = -Infinity;
  for (const v of values) {
    if (!Number.isFinite(v)) continue;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  if (!(min <= max)) return [0, 1];
  const lo = Math.floor(min * 10) / 10;
  const hi = Math.ceil(max * 10) / 10;
  return hi - lo < 0.2 ? [lo - 0.5, hi + 0.5] : [lo, hi];
}

function ForecastsView() {
  const manifest = useLoadedManifest();
  const mode = useThemeMode();
  const { params, set } = useQueryState();
  const windows = useMemo(() => parseTimeWindows(manifest.time_windows), [manifest.time_windows]);

  const grids = useMemo(() => modelGrid(manifest.models), [manifest.models]);
  const gridSizes = useMemo(() => regularGridSizes(manifest.models), [manifest.models]);
  const modelIndex = indexByName(manifest.models, params.get('model'));
  const model = manifest.models[modelIndex];
  const selected = model ? splitModelName(model.name) : null;
  const firstAvailable = Math.max(0, model?.forecast_available.findIndex(Boolean) ?? 0);
  const windowIndex = windowIndexFromParam(params.get('window'), windows.length, firstAvailable);
  const window = windows[windowIndex];
  const available = !!model?.forecast_available[windowIndex];

  const { data, error, isLoading, mutate } = useForecast(available ? modelIndex : null, available ? windowIndex : null);
  const current = data && data.model === model?.name && data.time_window === window?.text;
  const forecast = available ? data : undefined;
  const elapsed = useElapsed(isLoading);

  // Warm the neighbouring windows so stepping through them is instant.
  useEffect(() => {
    if (!current || !model) return;
    for (const w of [windowIndex + 1, windowIndex - 1]) {
      if (w >= 0 && w < windows.length && model.forecast_available[w]) prefetchForecast(modelIndex, w);
    }
  }, [current, model, modelIndex, windowIndex, windows.length]);

  const cells = useMemo(() => (forecast ? forecastCells(forecast) : null), [forecast]);
  // Quadtree cells differ in area by orders of magnitude: compare densities there.
  const [measureChoice, setMeasure] = useState<Measure | null>(null);
  const measure: Measure = measureChoice ?? (cells?.grid.type === 'quadtree' ? 'density' : 'rate');
  const values = useMemo(() => {
    if (!cells) return new Float64Array(0);
    const out = new Float64Array(cells.rates.length);
    for (let k = 0; k < out.length; k++) {
      const v = measure === 'density' ? (cells.rates[k] / cells.areas[k]) * DENSITY_AREA : cells.rates[k];
      out[k] = Math.log10(v);
    }
    return out;
  }, [cells, measure]);
  const domain = useMemo<[number, number]>(() => valueDomain(values), [values]);

  // The colour range is kept while stepping through windows of the same model.
  const [userRange, setUserRange] = useState<{ key: string; range: [number, number] } | null>(null);
  const rangeKey = `${model?.name}:${measure}`;
  const range = useMemo<[number, number]>(() => {
    if (!userRange || userRange.key !== rangeKey) return domain;
    const lo = clamp(userRange.range[0], domain[0], domain[1] - 0.1);
    const hi = clamp(userRange.range[1], lo + 0.1, domain[1]);
    return [lo, hi];
  }, [userRange, rangeKey, domain]);
  const [opacity, setOpacity] = useState(0.85);
  const [palette, setPalette] = usePersistentState<PaletteName>('floatcsep:palette', 'turbo', PALETTE_NAMES);
  const stops = paletteStops(palette, mode);
  const [showObserved, setShowObserved] = useState(true);

  const { catalog } = useObservedCatalog(manifest);
  const mask = useMemo(() => regionMask(manifest.region), [manifest.region]);
  const minMagnitude = manifest.mag_min ?? manifest.magnitudes[0] ?? -Infinity;
  const observed = useMemo(
    () => (catalog && window ? eventsInWindow(catalog, window, minMagnitude, mask) : null),
    [catalog, window, minMagnitude, mask],
  );

  const peak = useMemo(() => {
    if (!cells || cells.rates.length === 0) return null;
    let k = 0;
    for (let j = 1; j < values.length; j++) if (values[j] > values[k]) k = j;
    const [west, south, east, north] = cellBounds(cells.grid, k);
    return {
      value: 10 ** values[k],
      lon: (west + east) / 2,
      lat: (south + north) / 2,
    };
  }, [cells, values]);

  const magnitudeBins = useMemo(() => {
    if (!forecast) return null;
    const mags = forecast.magnitudes.filter((m): m is number => m !== null);
    const expected = forecast.magnitude_rates.slice(0, mags.length);
    let counts: number[] | null = null;
    if (catalog && observed) {
      counts = mags.map(() => 0);
      for (const i of observed) {
        const m = catalog.mag[i];
        let k = -1;
        for (let b = 0; b < mags.length; b++) if (m >= mags[b] - 1e-9) k = b;
        if (k >= 0) counts[k]++;
      }
    }
    return { mags, expected, counts };
  }, [forecast, catalog, observed]);

  if (manifest.models.length === 0) {
    return (
      <>
        <PageHeader title="Forecasts" />
        <Card>
          <EmptyState icon={FileX2} title="No models" description="This experiment has no forecasting models." />
        </Card>
      </>
    );
  }

  const selectWindow = (index: number) => set({ window: index + 1 });
  const windowOptions = windows.map((w) => ({
    value: String(w.index),
    label: `${w.label} · ${formatDate(w.start)} → ${formatDate(w.end)}${model.forecast_available[w.index] ? '' : ' (no forecast)'}`,
  }));

  let body: ReactNode;
  if (!available) {
    const registered = model.forecasts[windowIndex];
    body = (
      <Card>
        <EmptyState
          icon={FileX2}
          title={`No forecast for ${window?.label ?? 'this window'}`}
          description={
            registered
              ? `${model.name} has no forecast file at ${registered}. Run the experiment to create it.`
              : `${model.name} has no forecast registered for this time window.`
          }
        />
      </Card>
    );
  } else if (error && !current) {
    body = (
      <Card>
        <ErrorState
          title="The forecast could not be loaded"
          message={error.message}
          details={error.details}
          onRetry={() => mutate()}
        />
      </Card>
    );
  } else if (!forecast || !cells) {
    body = (
      <Card>
        <LoadingState
          title={
            model.is_catalog_forecast
              ? 'Computing expected rates from the simulated catalogs…'
              : 'Reading the forecast…'
          }
          description={
            elapsed >= 3 ? `${elapsed}s — large forecasts take a while the first time; results are cached.` : undefined
          }
          className="min-h-[420px]"
        />
      </Card>
    );
  } else {
    const stale = !current;
    body = (
      <>
        <StatGrid className="mb-5">
          <StatTile
            label="Expected events"
            value={formatRate(forecast.total)}
            caption={`Σλ over ${formatInt(forecast.n_cells)} cells`}
          />
          <StatTile
            label="Observed events"
            value={observed ? formatInt(observed.length) : '—'}
            caption={
              observed
                ? `M ≥ ${minMagnitude.toFixed(magnitudeDecimals([minMagnitude]))} in the region`
                : manifest.catalog.available
                  ? 'loading catalog…'
                  : 'no catalog'
            }
          />
          <StatTile
            label={measure === 'density' ? 'Peak rate density' : 'Peak cell rate'}
            value={peak ? formatSci(peak.value) : '—'}
            caption={
              peak
                ? `${measure === 'density' ? 'per 10⁴ km² · ' : ''}${formatLatLon(peak.lat, peak.lon, 1)}`
                : undefined
            }
          />
          <StatTile
            label="Active cells"
            value={formatInt(forecast.n_active)}
            caption={`${((forecast.n_active / Math.max(1, forecast.n_cells)) * 100).toFixed(forecast.n_active === forecast.n_cells ? 0 : 1)}% with λ > 0`}
          />
          <StatTile
            label="Forecast type"
            value={forecast.kind === 'catalog' ? 'Catalog' : 'Gridded'}
            caption={
              forecast.n_catalogs
                ? `${formatInt(forecast.n_catalogs)} simulated catalogs`
                : cells.grid.type === 'quadtree'
                  ? `quadtree, levels ${cells.grid.levels[0]}–${cells.grid.levels[cells.grid.levels.length - 1]}`
                  : `${forecast.dh?.toFixed(2)}° cells`
            }
          />
          <StatTile
            label="Time window"
            value={window.label}
            caption={`${formatDuration(window.end - window.start)} from ${formatDate(window.start)}`}
          />
        </StatGrid>

        <div className="grid gap-5 xl:grid-cols-12">
          <Card className="flex flex-col xl:col-span-8">
            <CardHeader
              title={`${model.name} · ${window.label}`}
              description={
                <>
                  {measure === 'density' ? 'Expected events per 10⁴ km²' : 'Expected events per cell'},{' '}
                  {formatDate(window.start)} → {formatDate(window.end)} ·{' '}
                  <code className="text-2xs" title={forecast.path}>
                    {forecast.path.split('/').pop()}
                  </code>
                </>
              }
              actions={stale && <Badge tone="info">Loading {windows[windowIndex].label}…</Badge>}
            />
            <div
              className={cn('flex min-h-[560px] flex-1 flex-col p-3 transition-opacity', stale && 'opacity-60')}
              aria-busy={stale}
            >
              <ErrorBoundary label="The forecast map">
                <ForecastMap
                  cells={cells}
                  values={values}
                  measure={measure}
                  range={range}
                  stops={stops}
                  opacity={opacity}
                  observed={showObserved && catalog && observed ? { catalog, indices: observed } : null}
                />
              </ErrorBoundary>
            </div>
          </Card>

          <div className="flex flex-col gap-5 xl:col-span-4">
            <Card>
              <CardHeader
                title="Colour scale"
                description={
                  <>
                    log<sub>10</sub> of {measure === 'density' ? 'events per 10⁴ km²' : 'λ per cell'} · values outside
                    the range are clamped
                  </>
                }
                actions={
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={range[0] === domain[0] && range[1] === domain[1]}
                    onClick={() => setUserRange(null)}
                  >
                    <RotateCcw /> Reset
                  </Button>
                }
              />
              <CardBody className="space-y-4 pt-3">
                <SegmentedControl<Measure>
                  label="Measure"
                  size="md"
                  className="w-full [&>button]:flex-1"
                  value={measure}
                  onChange={(value) => {
                    setMeasure(value);
                    setUserRange(null);
                  }}
                  options={[
                    { value: 'rate', label: 'Events per cell' },
                    { value: 'density', label: 'Rate density' },
                  ]}
                />
                <ErrorBoundary label="The histogram">
                  <RateHistogram logRates={values} domain={domain} range={range} stops={stops} />
                </ErrorBoundary>
                <div>
                  <div className="mb-1 h-2 rounded-sm ring-1 ring-line" style={{ background: rampGradient(stops) }} />
                  <RangeSlider
                    label="Colour range"
                    min={domain[0]}
                    max={domain[1]}
                    step={0.1}
                    value={range}
                    onChange={(value) => setUserRange({ key: rangeKey, range: value })}
                    formatValue={(v) => v.toFixed(1)}
                  />
                  <div className="mt-1 flex justify-between text-xs tabular text-ink-2">
                    <span>{range[0].toFixed(1)}</span>
                    <span>{range[1].toFixed(1)}</span>
                  </div>
                </div>
                <PalettePicker value={palette} onChange={setPalette} />
                <Slider
                  label="Layer opacity"
                  min={0.2}
                  max={1}
                  step={0.05}
                  value={opacity}
                  onChange={setOpacity}
                  formatValue={(v) => `${Math.round(v * 100)}%`}
                />
              </CardBody>
            </Card>

            {magnitudeBins && magnitudeBins.mags.length > 0 && (
              <ChartCard
                title="Magnitude distribution"
                description="Expected vs observed events per magnitude bin"
                table={
                  <DataTable
                    caption="Expected and observed events per magnitude bin"
                    columns={[
                      {
                        key: 'm',
                        header: 'Magnitude',
                        numeric: true,
                        render: (k: number) => magnitudeBinLabel(magnitudeBins.mags, k),
                      },
                      {
                        key: 'e',
                        header: 'Expected',
                        align: 'right',
                        numeric: true,
                        render: (k: number) => formatRate(magnitudeBins.expected[k]),
                        csv: (k: number) => magnitudeBins.expected[k],
                      },
                      ...(magnitudeBins.counts
                        ? [
                            {
                              key: 'o',
                              header: 'Observed',
                              align: 'right' as const,
                              numeric: true,
                              render: (k: number) => formatInt(magnitudeBins.counts![k]),
                            },
                          ]
                        : []),
                    ]}
                    rows={magnitudeBins.mags.map((_, k) => k)}
                    rowKey={(k) => String(k)}
                  />
                }
              >
                <MagnitudeRateChart
                  magnitudes={magnitudeBins.mags}
                  expected={magnitudeBins.expected}
                  observed={magnitudeBins.counts}
                  height={250}
                />
              </ChartCard>
            )}
          </div>
        </div>
      </>
    );
  }

  return (
    <>
      <PageHeader
        title="Forecasts"
        description="Expected number of earthquakes per cell for each model and time window."
      />

      <FilterBar>
        {grids && selected?.grid ? (
          <>
            <Select
              label="Model"
              className="w-full sm:w-52"
              value={selected.model}
              onChange={(value) => {
                const index = grids.indexOf(value, selected.grid!);
                if (index >= 0) set({ model: manifest.models[index].name });
              }}
              options={grids.models.map((name) => ({
                value: name,
                label: name,
                disabled: grids.indexOf(name, selected.grid!) < 0,
              }))}
            />
            <Select
              label="Grid"
              className="w-full sm:w-48"
              value={selected.grid}
              onChange={(value) => {
                const index = grids.indexOf(selected.model, value);
                if (index >= 0) set({ model: manifest.models[index].name });
              }}
              options={grids.grids.map((grid) => ({
                value: grid,
                label: gridLabel(grid, gridSizes),
                disabled: grids.indexOf(selected.model, grid) < 0,
              }))}
            />
          </>
        ) : (
          <Select
            label="Model"
            className="w-full sm:w-60"
            value={String(modelIndex)}
            onChange={(value) => set({ model: manifest.models[Number(value)].name })}
            options={manifest.models.map((m, i) => ({
              value: String(i),
              label: `${m.name}${m.is_catalog_forecast ? ' (catalog-based)' : ''}`,
            }))}
          />
        )}
        <Select
          label="Time window"
          className="w-full sm:w-[22rem]"
          value={String(windowIndex)}
          onChange={(value) => selectWindow(Number(value))}
          options={windowOptions}
          addon={
            <>
              <Button
                size="icon"
                className="size-9"
                aria-label="Previous time window"
                disabled={windowIndex === 0}
                onClick={() => selectWindow(windowIndex - 1)}
              >
                <ChevronLeft />
              </Button>
              <Button
                size="icon"
                className="size-9"
                aria-label="Next time window"
                disabled={windowIndex >= windows.length - 1}
                onClick={() => selectWindow(windowIndex + 1)}
              >
                <ChevronRight />
              </Button>
            </>
          }
        />
        <Switch className="h-9" checked={showObserved} onChange={setShowObserved} label="Show observed events" />
      </FilterBar>

      {body}
    </>
  );
}
