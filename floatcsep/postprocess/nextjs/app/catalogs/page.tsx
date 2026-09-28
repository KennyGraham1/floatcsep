'use client';

import { FileX2, RotateCcw } from 'lucide-react';
import dynamic from 'next/dynamic';
import { useMemo, useState } from 'react';
import { EventsTable } from '@/components/catalog/EventsTable';
import { ChartCard } from '@/components/charts/ChartCard';
import EventsPerWindowChart from '@/components/charts/EventsPerWindowChart';
import MagnitudeFrequencyChart from '@/components/charts/MagnitudeFrequencyChart';
import MagnitudeTimeChart from '@/components/charts/MagnitudeTimeChart';
import { FilterBar, PageHeader } from '@/components/layout/PageHeader';
import { TimeWindowsTable } from '@/components/overview/TimeWindowsTable';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { Slider } from '@/components/ui/Slider';
import { StatGrid, StatTile } from '@/components/ui/StatTile';
import { EmptyState, ErrorState, LoadingState, Skeleton } from '@/components/ui/States';
import { useElapsed } from '@/hooks/useElapsed';
import { useObservedCatalog } from '@/hooks/useObservedCatalog';
import { bValue, countPerWindow, filterEvents, INPUT, magnitudeFrequency, TEST, type Catalog } from '@/lib/catalog';
import { useLoadedManifest } from '@/lib/contexts/ManifestContext';
import { formatInt, formatMagnitude, magnitudeDecimals } from '@/lib/format';
import { formatDate, formatDuration, parseTimeWindows, parseUtc, windowsAreDisjoint } from '@/lib/time';
import type { Manifest } from '@/lib/types';
import { extent } from '@/lib/utils';

const CatalogMap = dynamic(() => import('@/components/maps/CatalogMap'), {
  ssr: false,
  loading: () => <Skeleton className="h-[440px] w-full rounded-lg" />,
});

type Period = 'all' | 'input' | 'test';
const MFD_BIN = 0.1;

export default function CatalogPage() {
  const manifest = useLoadedManifest();
  const { catalog, error, isLoading, reload } = useObservedCatalog(manifest);
  const elapsed = useElapsed(isLoading);

  const header = (
    <PageHeader
      title="Catalog"
      description={
        manifest.catalog.path ? (
          <>
            Observed events from <code className="text-xs text-ink-2">{manifest.catalog.path}</code>. Times are UTC.
          </>
        ) : (
          'Observed events of the experiment.'
        )
      }
    />
  );

  if (!manifest.catalog.available) {
    return (
      <>
        {header}
        <Card>
          <EmptyState
            icon={FileX2}
            title="No catalog file"
            description={
              manifest.catalog.path
                ? `The catalog ${manifest.catalog.path} was not found in the results directory. Run the experiment to download or filter it.`
                : 'This experiment does not define a catalog.'
            }
          />
        </Card>
      </>
    );
  }

  if (error) {
    return (
      <>
        {header}
        <Card>
          <ErrorState
            title="The catalog could not be loaded"
            message={error.message}
            details={error.details}
            onRetry={() => reload()}
          />
        </Card>
      </>
    );
  }

  if (!catalog) {
    return (
      <>
        {header}
        <Card>
          <LoadingState
            title="Reading the catalog…"
            description={
              elapsed >= 3
                ? `${elapsed}s — the first load parses the file with floatCSEP; later loads are cached.`
                : undefined
            }
          />
        </Card>
      </>
    );
  }

  return (
    <>
      {header}
      <CatalogView manifest={manifest} catalog={catalog} />
    </>
  );
}

function CatalogView({ manifest, catalog }: { manifest: Manifest; catalog: Catalog }) {
  const windows = useMemo(() => parseTimeWindows(manifest.time_windows), [manifest.time_windows]);
  const startMs = parseUtc(manifest.start_date);
  const endMs = parseUtc(manifest.end_date);

  const magExtent = useMemo(() => extent(catalog.mag) ?? [0, 10], [catalog]);
  const magFloor = Math.floor(magExtent[0] * 10) / 10;
  const magCeil = Math.max(magFloor + 0.1, Math.floor(magExtent[1] * 10) / 10);

  const [period, setPeriod] = useState<Period>('all');
  const [minMagnitude, setMinMagnitude] = useState(magFloor);
  const [zoom, setZoom] = useState<'all' | 'experiment'>('all');

  const indices = useMemo(
    () => filterEvents(catalog, { input: period !== 'test', test: period !== 'input', minMagnitude }),
    [catalog, period, minMagnitude],
  );

  const stats = useMemo(() => {
    let input = 0;
    let largest = -1;
    let first = Infinity;
    let last = -Infinity;
    for (const i of indices) {
      if (catalog.kind[i] === INPUT) input++;
      if (largest < 0 || catalog.mag[i] > catalog.mag[largest]) largest = i;
      if (catalog.time[i] < first) first = catalog.time[i];
      if (catalog.time[i] > last) last = catalog.time[i];
    }
    const mags = extent(Array.from(indices, (i) => catalog.mag[i]));
    return { input, test: indices.length - input, largest, first, last, mags };
  }, [catalog, indices]);

  const mfd = useMemo(() => magnitudeFrequency(catalog.mag, indices, MFD_BIN), [catalog, indices]);
  const completeness = Math.max(minMagnitude, manifest.mag_min ?? -Infinity);
  const b = useMemo(() => bValue(catalog.mag, indices, completeness), [catalog, indices, completeness]);

  const testIndices = useMemo(() => indices.filter((i) => catalog.kind[i] === TEST), [catalog, indices]);
  const counts = useMemo(() => countPerWindow(catalog, testIndices, windows), [catalog, testIndices, windows]);

  const zoomRange: [number, number] | null =
    zoom === 'experiment' && Number.isFinite(startMs) && Number.isFinite(endMs) ? [startMs, endMs] : null;
  const filtered = period !== 'all' || minMagnitude > magFloor;

  return (
    <>
      <FilterBar>
        <div className="flex flex-col gap-1.5">
          <span className="text-xs font-medium text-ink-2">Events</span>
          <SegmentedControl<Period>
            label="Events to show"
            size="md"
            value={period}
            onChange={setPeriod}
            options={[
              { value: 'all', label: 'All' },
              { value: 'input', label: 'Before start' },
              { value: 'test', label: 'Experiment period' },
            ]}
          />
        </div>
        <Slider
          label="Minimum magnitude"
          className="w-56"
          min={magFloor}
          max={magCeil}
          step={0.1}
          value={minMagnitude}
          onChange={setMinMagnitude}
          formatValue={(v) => `M ≥ ${v.toFixed(1)}`}
        />
        <div className="ml-auto flex items-center gap-3 self-center">
          <span className="text-xs tabular text-ink-3">
            {formatInt(indices.length)} of {formatInt(catalog.n)} events
          </span>
          <Button
            variant="ghost"
            size="sm"
            disabled={!filtered}
            onClick={() => {
              setPeriod('all');
              setMinMagnitude(magFloor);
            }}
          >
            <RotateCcw /> Reset
          </Button>
        </div>
      </FilterBar>

      <StatGrid className="mb-5">
        <StatTile
          label="Events"
          value={formatInt(indices.length)}
          caption={filtered ? 'matching the filters' : 'in the catalog'}
        />
        <StatTile label="Before start" value={formatInt(stats.input)} caption={`before ${manifest.start_date}`} />
        <StatTile label="Experiment period" value={formatInt(stats.test)} caption={`from ${manifest.start_date}`} />
        <StatTile
          label="Largest event"
          value={stats.largest >= 0 ? `M ${formatMagnitude(catalog.mag[stats.largest])}` : '—'}
          caption={stats.largest >= 0 ? formatDate(catalog.time[stats.largest]) : undefined}
        />
        <StatTile
          label="Magnitude range"
          value={stats.mags ? `${formatMagnitude(stats.mags[0])}–${formatMagnitude(stats.mags[1])}` : '—'}
          caption={b ? `b ≈ ${b.b.toFixed(2)} ± ${b.sigma.toFixed(2)}` : 'magnitude'}
        />
        <StatTile
          label="Time span"
          value={Number.isFinite(stats.first) ? formatDuration(stats.last - stats.first) : '—'}
          caption={Number.isFinite(stats.first) ? `${formatDate(stats.first)} → ${formatDate(stats.last)}` : undefined}
        />
      </StatGrid>

      <div className="mb-5 grid gap-5 xl:grid-cols-12">
        <Card className="xl:col-span-7">
          <CardHeader
            title="Epicentres"
            description="Marker size grows with magnitude · hover an event for details · click the map to zoom with the wheel"
          />
          <div className="p-3">
            <ErrorBoundary label="The map">
              <CatalogMap
                catalog={catalog}
                indices={indices}
                height={440}
                fallbackBounds={manifest.region?.bbox ?? null}
              />
            </ErrorBoundary>
          </div>
        </Card>
        <ChartCard
          className="xl:col-span-5"
          title="Magnitude–frequency distribution"
          description={
            b
              ? `b ≈ ${b.b.toFixed(2)} ± ${b.sigma.toFixed(2)} (Aki–Utsu, M ≥ ${b.completeness.toFixed(magnitudeDecimals([b.completeness]))}, ${formatInt(b.n)} events)`
              : 'Gutenberg–Richter plot of the selected events'
          }
          table={
            <DataTable
              caption="Events per magnitude bin"
              columns={[
                {
                  key: 'm',
                  header: 'Magnitude bin',
                  numeric: true,
                  render: (k: number) => `${mfd.magnitudes[k].toFixed(1)}–${(mfd.magnitudes[k] + MFD_BIN).toFixed(1)}`,
                },
                {
                  key: 'n',
                  header: 'Events',
                  align: 'right',
                  numeric: true,
                  render: (k: number) => formatInt(mfd.incremental[k]),
                },
                {
                  key: 'c',
                  header: 'Events ≥ M',
                  align: 'right',
                  numeric: true,
                  render: (k: number) => formatInt(mfd.cumulative[k]),
                },
              ]}
              rows={mfd.magnitudes.map((_, k) => k)}
              rowKey={(k) => String(k)}
            />
          }
        >
          {mfd.magnitudes.length > 0 ? (
            <MagnitudeFrequencyChart mfd={mfd} binWidth={MFD_BIN} height={408} />
          ) : (
            <p className="py-16 text-center text-xs text-ink-3">No events match the filters.</p>
          )}
        </ChartCard>
      </div>

      <ChartCard
        className="mb-5"
        title="Magnitude over time"
        description={
          windows.length > 1 && windowsAreDisjoint(windows)
            ? 'Shaded bands mark alternate forecast time windows · drag the slider or scroll to zoom'
            : 'Drag the slider or scroll to zoom'
        }
        actions={
          <SegmentedControl<'all' | 'experiment'>
            label="Time range"
            value={zoom}
            onChange={setZoom}
            options={[
              { value: 'all', label: 'All time' },
              { value: 'experiment', label: 'Experiment' },
            ]}
          />
        }
        table={<EventsTable catalog={catalog} indices={indices} caption="Catalog events" />}
      >
        <MagnitudeTimeChart
          catalog={catalog}
          indices={indices}
          windows={windows}
          startMs={startMs}
          zoom={zoomRange}
          height={380}
        />
      </ChartCard>

      <div className="grid gap-5 xl:grid-cols-2">
        {windows.length > 1 && (
          <ChartCard
            title="Events per time window"
            description="Experiment-period events inside each forecast window"
            table={<TimeWindowsTable windows={windows} counts={counts} />}
          >
            <EventsPerWindowChart windows={windows} counts={counts} height={300} />
          </ChartCard>
        )}
        <Card className={windows.length > 1 ? undefined : 'xl:col-span-2'}>
          <CardHeader title="Largest events" description="The ten largest events matching the filters" />
          <EventsTable
            catalog={catalog}
            indices={indices}
            limit={10}
            caption="Largest events"
            compact={windows.length > 1}
          />
        </Card>
      </div>
    </>
  );
}
