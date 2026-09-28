'use client';

import { ChevronLeft, ChevronRight, Download, ExternalLink, FileChartColumn, Maximize2 } from 'lucide-react';
import { Suspense, useMemo, useState } from 'react';
import { FilterBar, PageHeader } from '@/components/layout/PageHeader';
import { shortFunctionName } from '@/components/overview/TestsTable';
import { CoverageMatrix } from '@/components/results/CoverageMatrix';
import { FigureImage } from '@/components/results/FigureImage';
import { Badge } from '@/components/ui/Badge';
import { Button, LinkButton } from '@/components/ui/Button';
import { Card, CardBody, CardHeader } from '@/components/ui/Card';
import { DefinitionList } from '@/components/ui/DefinitionList';
import { Lightbox, type LightboxItem } from '@/components/ui/Lightbox';
import { Select } from '@/components/ui/Select';
import { EmptyState, Skeleton } from '@/components/ui/States';
import { useQueryState, windowIndexFromParam } from '@/hooks/useQueryState';
import { useLoadedManifest } from '@/lib/contexts/ManifestContext';
import { pluralize } from '@/lib/format';
import { formatDate, parseTimeWindows } from '@/lib/time';
import type { ResultFigure, Test } from '@/lib/types';
import { figureUrl } from '@/lib/utils';

export default function ResultsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96 w-full rounded-xl" />}>
      <ResultsView />
    </Suspense>
  );
}

function isEmptyValue(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (Array.isArray(value)) return value.every(isEmptyValue);
  if (typeof value === 'object') return Object.keys(value as object).length === 0;
  return false;
}

/** Pretty-printed JSON, or null (so the definition row is hidden) when empty. */
function jsonBlock(value: unknown) {
  if (isEmptyValue(value)) return null;
  return (
    <pre className="scrollbar-thin max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-md border bg-surface-2 px-2.5 py-2 font-mono text-2xs leading-4 text-ink-2">
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function TestDetails({ test }: { test: Test }) {
  return (
    <DefinitionList
      layout="stacked"
      items={[
        {
          label: 'Evaluation',
          value: test.func && (
            <code className="text-xs text-ink-2" title={test.func}>
              {/* Allow line breaks after dots in long dotted names. */}
              {shortFunctionName(test.func)?.replace(/\./g, '.\u200b')}
            </code>
          ),
        },
        { label: 'Reference model', value: test.ref_model },
        { label: 'Arguments', value: jsonBlock(test.func_kwargs) },
        {
          label: 'Plot functions',
          value: test.plot_func.length > 0 && (
            <span className="text-xs text-ink-2">{test.plot_func.map((f) => f.split('.').pop()).join(', ')}</span>
          ),
        },
        { label: 'Plot arguments', value: jsonBlock(test.plot_args) },
      ]}
    />
  );
}

function ResultsView() {
  const manifest = useLoadedManifest();
  const { params, set } = useQueryState();
  const windows = useMemo(() => parseTimeWindows(manifest.time_windows), [manifest.time_windows]);
  const [lightbox, setLightbox] = useState<number | null>(null);

  const { byKey, counts, testsWithFigures } = useMemo(() => {
    const byKey = new Map<string, { summary: ResultFigure | null; models: ResultFigure[] }>();
    const counts = new Map<string, number>();
    for (const figure of manifest.results) {
      const key = `${figure.window}|${figure.test}`;
      const entry = byKey.get(key) ?? { summary: null, models: [] };
      if (figure.model === null) entry.summary = figure;
      else entry.models.push(figure);
      byKey.set(key, entry);
      counts.set(key, (counts.get(key) ?? 0) + 1);
    }
    // Keep the manifest's model order for per-model figures.
    const order = new Map(manifest.models.map((m, i) => [m.name, i]));
    byKey.forEach((entry) => entry.models.sort((a, b) => (order.get(a.model!) ?? 0) - (order.get(b.model!) ?? 0)));
    const testsWithFigures = new Set(manifest.results.map((f) => f.test));
    return { byKey, counts, testsWithFigures };
  }, [manifest.results, manifest.models]);

  if (manifest.results.length === 0) {
    return (
      <>
        <PageHeader title="Results" description="Evaluation figures of the experiment." />
        <Card>
          <EmptyState
            icon={FileChartColumn}
            title="No result figures yet"
            description={
              <>
                Evaluation figures appear here once the experiment has run. Create them with{' '}
                <code className="text-ink-2">floatcsep run config.yml</code> or{' '}
                <code className="text-ink-2">floatcsep plot config.yml</code>.
              </>
            }
          />
        </Card>
      </>
    );
  }

  const tests = manifest.tests.length > 0 ? manifest.tests : Array.from(testsWithFigures, (name) => ({ name }) as Test);
  const defaultTest = tests.find((t) => testsWithFigures.has(t.name))?.name ?? tests[0].name;
  const testName = tests.some((t) => t.name === params.get('test')) ? params.get('test')! : defaultTest;
  const test = tests.find((t) => t.name === testName)!;

  // Default to the latest window with figures for this test (e.g. cumulative tests).
  let latest = 0;
  windows.forEach((w) => {
    if (counts.has(`${w.index}|${testName}`)) latest = w.index;
  });
  const windowIndex = windowIndexFromParam(params.get('window'), windows.length, latest);
  const window = windows[windowIndex];
  const entry = byKey.get(`${windowIndex}|${testName}`) ?? { summary: null, models: [] };

  const items: LightboxItem[] = [
    ...(entry.summary ? [entry.summary] : []),
    ...entry.models,
  ].map((figure) => ({
    src: figureUrl(figure.path),
    downloadHref: figureUrl(figure.path, true),
    title: figure.model ? `${testName} · ${figure.model}` : testName,
    subtitle: `${window.label} · ${formatDate(window.start)} → ${formatDate(window.end)}`,
  }));

  const selectWindow = (index: number) => set({ window: index + 1 });

  return (
    <>
      <PageHeader
        title="Results"
        description="Figures produced by the evaluation tests. Click a figure to enlarge it."
      />

      <FilterBar>
        <Select
          label="Test"
          className="w-full sm:w-64"
          value={testName}
          onChange={(value) => set({ test: value })}
          options={tests.map((t) => ({
            value: t.name,
            label: testsWithFigures.has(t.name) ? t.name : `${t.name} (no figures)`,
          }))}
        />
        <Select
          label="Time window"
          className="w-full sm:w-[22rem]"
          value={String(windowIndex)}
          onChange={(value) => selectWindow(Number(value))}
          options={windows.map((w) => ({
            value: String(w.index),
            label: `${w.label} · ${formatDate(w.start)} → ${formatDate(w.end)}${counts.has(`${w.index}|${testName}`) ? '' : ' (no figures)'}`,
          }))}
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
      </FilterBar>

      <div className="grid gap-5 xl:grid-cols-12">
        <div className="flex min-w-0 flex-col gap-5 xl:col-span-8">
          <Card>
            <CardHeader
              title={`${testName} · ${window.label}`}
              description={
                entry.summary
                  ? `Summary figure · ${formatDate(window.start)} → ${formatDate(window.end)}`
                  : `${formatDate(window.start)} → ${formatDate(window.end)}`
              }
              actions={
                entry.summary && (
                  <>
                    <Button size="sm" variant="ghost" onClick={() => setLightbox(0)}>
                      <Maximize2 /> Expand
                    </Button>
                    <LinkButton size="sm" variant="ghost" href={figureUrl(entry.summary.path)} target="_blank" rel="noopener noreferrer">
                      <ExternalLink /> Open
                    </LinkButton>
                    <LinkButton size="sm" variant="ghost" href={figureUrl(entry.summary.path, true)}>
                      <Download /> Download
                    </LinkButton>
                  </>
                )
              }
            />
            <CardBody>
              {entry.summary ? (
                <FigureImage
                  key={entry.summary.path}
                  src={figureUrl(entry.summary.path)}
                  alt={`${testName} result for ${window.label}`}
                  onOpen={() => setLightbox(0)}
                  className="mx-auto max-w-4xl"
                />
              ) : (
                <EmptyState
                  icon={FileChartColumn}
                  title="No summary figure"
                  description={
                    entry.models.length > 0
                      ? 'This test only has per-model figures for this window (below).'
                      : `${testName} has no figures for ${window.label}. Pick a highlighted cell in the coverage chart.`
                  }
                />
              )}
            </CardBody>
          </Card>

          {entry.models.length > 0 && (
            <Card>
              <CardHeader
                title="Per-model figures"
                description={`${pluralize(entry.models.length, 'figure')} for ${window.label}`}
              />
              <CardBody>
                <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-3">
                  {entry.models.map((figure, k) => {
                    const index = (entry.summary ? 1 : 0) + k;
                    return (
                      <figure key={figure.path} className="min-w-0">
                        <FigureImage
                          src={figureUrl(figure.path)}
                          alt={`${testName} result of ${figure.model} for ${window.label}`}
                          onOpen={() => setLightbox(index)}
                        />
                        <figcaption className="mt-2 flex items-center justify-between gap-2 text-xs">
                          <span className="truncate font-medium text-ink">{figure.model}</span>
                          <a href={figureUrl(figure.path, true)} className="link shrink-0 text-ink-3" aria-label={`Download ${figure.model} figure`}>
                            Download
                          </a>
                        </figcaption>
                      </figure>
                    );
                  })}
                </div>
              </CardBody>
            </Card>
          )}
        </div>

        <div className="flex min-w-0 flex-col gap-5 xl:col-span-4">
          <Card>
            <CardHeader
              title="Test details"
              description={test.func ? undefined : 'Configuration of the evaluation'}
              actions={testsWithFigures.has(testName) ? <Badge tone="info">{pluralize(manifest.results.filter((f) => f.test === testName).length, 'figure')}</Badge> : undefined}
            />
            <CardBody>
              <TestDetails test={test} />
            </CardBody>
          </Card>
          {windows.length > 1 && (
            <Card>
              <CardHeader title="Coverage" description="Figures available per test and time window" />
              <CardBody>
                <CoverageMatrix
                  tests={tests.map((t) => t.name)}
                  windows={windows}
                  counts={counts}
                  selected={{ test: testName, window: windowIndex }}
                  onSelect={(t, w) => set({ test: t, window: w + 1 })}
                />
              </CardBody>
            </Card>
          )}
        </div>
      </div>

      <Lightbox items={items} index={lightbox} onIndexChange={setLightbox} />
    </>
  );
}
