'use client';

import dynamic from 'next/dynamic';
import { useMemo } from 'react';
import { ChartCard } from '@/components/charts/ChartCard';
import TimeWindowsChart from '@/components/charts/TimeWindowsChart';
import { PageHeader } from '@/components/layout/PageHeader';
import { ModelsTable } from '@/components/overview/ModelsTable';
import { TestsTable } from '@/components/overview/TestsTable';
import { TimeWindowsTable } from '@/components/overview/TimeWindowsTable';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DefinitionList } from '@/components/ui/DefinitionList';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import { StatGrid, StatTile } from '@/components/ui/StatTile';
import { Skeleton } from '@/components/ui/States';
import { useObservedCatalog } from '@/hooks/useObservedCatalog';
import { countPerWindow, TEST } from '@/lib/catalog';
import { useLoadedManifest } from '@/lib/contexts/ManifestContext';
import { formatInt, pluralize } from '@/lib/format';
import { formatDuration, parseTimeWindows, parseUtc } from '@/lib/time';
import { doiUrl } from '@/lib/utils';

const MAP_HEIGHT = 380;

const RegionMap = dynamic(() => import('@/components/maps/RegionMap'), {
  ssr: false,
  loading: () => <Skeleton className="h-[380px] w-full rounded-lg" />,
});

function Mono({ children }: { children: string }) {
  return <code className="break-all text-xs text-ink-2">{children}</code>;
}

export default function OverviewPage() {
  const manifest = useLoadedManifest();
  const windows = useMemo(() => parseTimeWindows(manifest.time_windows), [manifest.time_windows]);
  const { catalog } = useObservedCatalog(manifest);

  const counts = useMemo(() => {
    if (!catalog) return null;
    const test: number[] = [];
    for (let i = 0; i < catalog.n; i++) if (catalog.kind[i] === TEST) test.push(i);
    return countPerWindow(catalog, test, windows);
  }, [catalog, windows]);

  const start = parseUtc(manifest.start_date);
  const end = parseUtc(manifest.end_date);
  const durations = new Set(windows.map((w) => w.end - w.start));
  const windowCaption =
    windows.length === 0
      ? 'none defined'
      : manifest.growth === 'cumulative' && windows.length > 1
        ? 'cumulative from the start'
        : durations.size === 1
          ? `${formatDuration(windows[0].end - windows[0].start)} each`
          : 'variable length';
  const catalogModels = manifest.models.filter((m) => m.is_catalog_forecast).length;
  const region = manifest.region;
  const cells = region?.origins?.length ?? null;

  const details = [
    { label: 'Experiment class', value: manifest.exp_class },
    { label: 'Testing period', value: `${manifest.start_date} → ${manifest.end_date}` },
    { label: 'Duration', value: Number.isFinite(end - start) ? formatDuration(end - start) : null },
    { label: 'Window horizon', value: manifest.horizon },
    { label: 'Window offset', value: manifest.offset },
    { label: 'Window growth', value: manifest.growth },
    { label: 'Run mode', value: manifest.run_mode },
    { label: 'Authors', value: manifest.authors },
    {
      label: 'DOI',
      value: manifest.doi && (
        <a href={doiUrl(manifest.doi)} target="_blank" rel="noopener noreferrer" className="link">
          {manifest.doi}
        </a>
      ),
    },
    { label: 'Journal', value: manifest.journal },
    {
      label: 'Manuscript DOI',
      value: manifest.manuscript_doi && (
        <a href={doiUrl(manifest.manuscript_doi)} target="_blank" rel="noopener noreferrer" className="link">
          {manifest.manuscript_doi}
        </a>
      ),
    },
    { label: 'Catalog', value: manifest.catalog.path && <Mono>{manifest.catalog.path}</Mono> },
    {
      label: 'Catalog DOI',
      value: manifest.catalog_doi && (
        <a href={doiUrl(manifest.catalog_doi)} target="_blank" rel="noopener noreferrer" className="link">
          {manifest.catalog_doi}
        </a>
      ),
    },
    { label: 'Configuration', value: manifest.config_file && <Mono>{manifest.config_file}</Mono> },
    { label: 'Models file', value: manifest.model_config && <Mono>{manifest.model_config}</Mono> },
    { label: 'Tests file', value: manifest.test_config && <Mono>{manifest.test_config}</Mono> },
    { label: 'Results directory', value: manifest.run_dir && <Mono>{manifest.run_dir}</Mono> },
    { label: 'License', value: manifest.license },
    { label: 'Last run', value: manifest.last_run },
  ];

  return (
    <>
      <PageHeader
        title={manifest.name}
        description={`Earthquake forecasting experiment tested from ${manifest.start_date} to ${manifest.end_date}.`}
      />

      <StatGrid className="mb-5">
        <StatTile label="Time windows" value={formatInt(windows.length)} caption={windowCaption} />
        <StatTile
          label="Models"
          value={formatInt(manifest.models.length)}
          caption={
            catalogModels === 0
              ? 'gridded forecasts'
              : catalogModels === manifest.models.length
                ? 'catalog-based forecasts'
                : `${catalogModels} catalog-based`
          }
        />
        <StatTile label="Tests" value={formatInt(manifest.tests.length)} caption={pluralize(manifest.results.length, 'result figure')} />
        <StatTile
          label="Magnitude range"
          value={manifest.mag_min !== null ? `M ${manifest.mag_min.toFixed(1)}–${manifest.mag_max?.toFixed(1) ?? '?'}` : '—'}
          caption={manifest.mag_bin ? `${manifest.magnitudes.length} bins of ${manifest.mag_bin}` : undefined}
        />
        <StatTile
          label="Depth range"
          value={manifest.depth_min !== null && manifest.depth_max !== null ? `${manifest.depth_min}–${manifest.depth_max} km` : '—'}
          caption="hypocentral depth"
        />
        <StatTile
          label="Region cells"
          value={cells !== null ? formatInt(cells) : '—'}
          caption={region?.dh ? `${region.dh}° grid${region.name ? ` · ${region.name}` : ''}` : region?.name ?? undefined}
        />
      </StatGrid>

      <div className="mb-5 grid gap-5 xl:grid-cols-12">
        <Card className="xl:col-span-5">
          <CardHeader title="Experiment details" description="Configuration of the experiment run" />
          <CardBody>
            <DefinitionList items={details} />
          </CardBody>
        </Card>
        <Card className="xl:col-span-7">
          <CardHeader
            title="Testing region"
            description={region?.name ? `Grid cells of ${region.name}` : 'Grid cells where forecasts are evaluated'}
          />
          <CardBody className="p-3">
            <ErrorBoundary label="The region map">
              {region ? (
                <RegionMap region={region} height={MAP_HEIGHT} />
              ) : (
                <p className="px-2 py-10 text-center text-xs text-ink-3">This experiment has no spatial region.</p>
              )}
            </ErrorBoundary>
          </CardBody>
        </Card>
      </div>

      {windows.length > 0 && (
        <ChartCard
          className="mb-5"
          title="Time windows"
          description={`${pluralize(windows.length, 'forecast window')} · dates in UTC${counts ? ' · hover for observed events' : ''}`}
          table={<TimeWindowsTable windows={windows} counts={counts} />}
        >
          <TimeWindowsChart windows={windows} counts={counts} />
        </ChartCard>
      )}

      <div className="grid gap-5 2xl:grid-cols-2">
        <Card>
          <CardHeader title="Models" description="Forecasting models under evaluation" />
          <ModelsTable manifest={manifest} />
        </Card>
        <Card>
          <CardHeader title="Tests" description="Evaluations applied to the forecasts" />
          <TestsTable manifest={manifest} />
        </Card>
      </div>
    </>
  );
}
