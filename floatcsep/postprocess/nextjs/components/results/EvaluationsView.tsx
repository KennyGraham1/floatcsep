'use client';

import { ChartColumnBig } from 'lucide-react';
import { useMemo } from 'react';
import { ChartCard } from '@/components/charts/ChartCard';
import EvaluationHeatmap, {
  DivergingLegend,
  ScoreLegend,
  type HeatCell,
  type HeatScale,
} from '@/components/charts/EvaluationHeatmap';
import IntervalChart, { type IntervalRow } from '@/components/charts/IntervalChart';
import { tooltipRow, tooltipTitle } from '@/components/charts/chartTheme';
import { FilterBar } from '@/components/layout/PageHeader';
import { Card } from '@/components/ui/Card';
import { DataTable } from '@/components/ui/DataTable';
import { Select } from '@/components/ui/Select';
import { EmptyState, ErrorState, LoadingState } from '@/components/ui/States';
import { useElapsed } from '@/hooks/useElapsed';
import { useQueryState, windowIndexFromParam } from '@/hooks/useQueryState';
import { useEvaluations } from '@/lib/api';
import { formatRate } from '@/lib/format';
import { gridLabel, modelGrid, regularGridSizes, shortGridNames, splitModelName } from '@/lib/modelGrid';
import { formatDate, parseTimeWindows, type TimeWindow } from '@/lib/time';
import type { EvaluationSummary, Manifest } from '@/lib/types';

const ALPHA = 0.05;

/** "2016" for a calendar year, "2014–2021" for whole years, else the window label. */
function windowName(w: TimeWindow): string {
  const start = new Date(w.start);
  const end = new Date(w.end);
  const whole = (d: Date) => d.getUTCMonth() === 0 && d.getUTCDate() === 1 && d.getUTCHours() === 0;
  if (whole(start) && whole(end)) {
    const years = end.getUTCFullYear() - start.getUTCFullYear();
    if (years === 1) return String(start.getUTCFullYear());
    if (years > 1) return `${start.getUTCFullYear()}–${end.getUTCFullYear() - 1}`;
  }
  return w.label;
}

function fmt(value: number | null, digits = 2): string {
  return value === null || !Number.isFinite(value) ? '—' : value.toFixed(digits);
}

function verdict(s: EvaluationSummary): string {
  if (s.kind === 'comparative') {
    return s.passed === true
      ? 'significantly better'
      : s.passed === false
        ? 'significantly worse'
        : 'not significantly different';
  }
  return s.passed === true ? 'not rejected' : s.passed === false ? 'rejected' : '—';
}

function describe(s: EvaluationSummary, where: string): string {
  const rows = [tooltipTitle(`${s.model} · ${where}`)];
  if (s.kind === 'number') {
    rows.push(tooltipRow(null, fmt(s.observed, 0), 'observed events'));
    rows.push(tooltipRow(null, s.expected === null ? '—' : formatRate(s.expected), 'expected events'));
    rows.push(tooltipRow(null, fmt(s.quantile, 3), `min(δ₁, δ₂) — ${verdict(s)}`));
  } else if (s.kind === 'consistency') {
    rows.push(tooltipRow(null, fmt(s.quantile, 3), `γ — ${verdict(s)}`));
    rows.push(tooltipRow(null, fmt(s.observed, 2), 'observed statistic'));
    rows.push(tooltipRow(null, fmt(s.expected, 2), 'simulated median'));
  } else if (s.kind === 'comparative') {
    rows.push(
      tooltipRow(
        null,
        s.observed === null ? '−∞' : `${s.observed >= 0 ? '+' : ''}${fmt(s.observed, 3)}`,
        'information gain per earthquake',
      ),
    );
    if (s.interval) rows.push(tooltipRow(null, `${fmt(s.interval[0], 3)} to ${fmt(s.interval[1], 3)}`, '95% interval'));
    rows.push(tooltipRow(null, s.reference ?? '—', `reference — ${verdict(s)}`));
  }
  return rows.join('');
}

function heatValue(s: EvaluationSummary): number | null {
  return s.kind === 'comparative' ? s.observed : s.quantile;
}

function heatLabel(s: EvaluationSummary): string {
  const v = heatValue(s);
  if (v === null || !Number.isFinite(v)) return s.kind === 'comparative' ? '−∞' : '—';
  if (s.kind === 'comparative') return `${v >= 0 ? '+' : ''}${v.toFixed(2)}`.replace('-0.00', '0.00');
  return v.toFixed(2);
}

export function EvaluationsView({ manifest }: { manifest: Manifest }) {
  const { data, error, isLoading, mutate } = useEvaluations(manifest.evaluations.length > 0);
  const elapsed = useElapsed(isLoading);
  const { params, set } = useQueryState();
  const windows = useMemo(() => parseTimeWindows(manifest.time_windows), [manifest.time_windows]);
  // Results can cover grids the experiment has no forecasts for (e.g. imported ones).
  const grids = useMemo(() => {
    const names = new Set(manifest.models.map((m) => m.name));
    for (const e of manifest.evaluations) names.add(e.model);
    return modelGrid([...names].map((name) => ({ name })));
  }, [manifest.models, manifest.evaluations]);
  const gridSizes = useMemo(() => regularGridSizes(manifest.models), [manifest.models]);

  const tests = useMemo(() => {
    const present = new Set((data ?? []).map((s) => s.test));
    const configured = manifest.tests.map((t) => t.name).filter((t) => present.has(t));
    return [
      ...configured,
      ...Array.from(present)
        .filter((t) => !configured.includes(t))
        .sort(),
    ];
  }, [data, manifest.tests]);

  if (manifest.evaluations.length === 0) {
    return (
      <Card>
        <EmptyState
          icon={ChartColumnBig}
          title="No evaluation results yet"
          description="Charts appear here once the experiment's tests have run (floatcsep run config.yml)."
        />
      </Card>
    );
  }
  if (error) {
    return (
      <Card>
        <ErrorState
          title="The evaluation results could not be loaded"
          message={error.message}
          details={error.details}
          onRetry={() => mutate()}
        />
      </Card>
    );
  }
  if (!data) {
    return (
      <Card>
        <LoadingState
          title="Reading the evaluation results…"
          description={
            elapsed >= 3
              ? `${elapsed}s — the first read summarizes every result file; later loads are cached.`
              : undefined
          }
        />
      </Card>
    );
  }

  const test = tests.includes(params.get('test') ?? '') ? params.get('test')! : tests[0];
  const ofTest = data.filter((s) => s.test === test);
  const kind = ofTest.find((s) => s.kind !== 'other')?.kind ?? 'other';
  const windowsWithResults = windows.filter((w) => ofTest.some((s) => s.window === w.index));
  // Default: the longest window (the whole period, when there are yearly ones too).
  const defaultWindow = windowsWithResults.reduce(
    (best, w) => (w.end - w.start > best.end - best.start ? w : best),
    windowsWithResults[0] ?? windows[0],
  );
  const windowIndex = windowIndexFromParam(params.get('window'), windows.length, defaultWindow?.index ?? 0);
  const window = windows[windowIndex];
  const gridName = grids
    ? grids.grids.includes(params.get('grid') ?? '')
      ? params.get('grid')!
      : grids.grids[0]
    : null;

  const models = grids ? grids.models : manifest.models.map((m) => m.name);
  const lookup = new Map(ofTest.map((s) => [`${s.model}\u0000${s.window}`, s]));
  const find = (model: string, grid: string | null, w: number) =>
    lookup.get(`${grid ? `${model}=${grid}` : model}\u0000${w}`);

  // Models without any result for this test (e.g. the reference of a T-test) are left out.
  const rowModels = models.filter((m) => ofTest.some((s) => (grids ? splitModelName(s.model).model : s.model) === m));

  const comparative = kind === 'comparative';
  const scale = (values: (number | null)[]): HeatScale => {
    if (!comparative) return { kind: 'score', threshold: kind === 'number' ? ALPHA / 2 : ALPHA };
    const finite = values
      .filter((v): v is number => v !== null && Number.isFinite(v))
      .map(Math.abs)
      .sort((a, b) => a - b);
    const limit = finite.length ? finite[Math.min(finite.length - 1, Math.floor(finite.length * 0.9))] : 1;
    return { kind: 'diverging', limit: Math.max(limit, 0.1) };
  };
  const scoreName = kind === 'number' ? 'Score min(δ₁, δ₂)' : 'Quantile γ';

  // Models x grids, for the selected window.
  const gridCells: HeatCell[] = [];
  if (grids) {
    rowModels.forEach((m, row) =>
      grids.grids.forEach((g, col) => {
        const s = find(m, g, windowIndex);
        if (s)
          gridCells.push({
            row,
            col,
            value: heatValue(s),
            passed: s.passed,
            label: heatLabel(s),
            tooltip: describe(s, `${g} · ${windowName(window)}`),
          });
      }),
    );
  }

  // Models x windows, for the selected grid, over the windows it has results for
  // (e.g. only the whole period for a grid evaluated elsewhere).
  const gridWindows = windowsWithResults.filter((w) => rowModels.some((m) => find(m, gridName, w.index)));
  const timeCells: HeatCell[] = [];
  rowModels.forEach((m, row) =>
    gridWindows.forEach((w, col) => {
      const s = find(m, gridName, w.index);
      if (s)
        timeCells.push({
          row,
          col,
          value: heatValue(s),
          passed: s.passed,
          label: heatLabel(s),
          tooltip: describe(s, `${gridName ? `${gridName} · ` : ''}${windowName(w)}`),
        });
    }),
  );

  // The selected window and grid, one row per model.
  const detail = rowModels
    .map((m) => ({ m, s: find(m, gridName, windowIndex) }))
    .filter((x): x is { m: string; s: EvaluationSummary } => !!x.s);
  const detailRows: IntervalRow[] = detail.map(({ m, s }) => ({
    label: m,
    lower: s.interval?.[0] ?? null,
    upper: s.interval?.[1] ?? null,
    centre: s.expected,
    observed: s.observed,
    passed: s.passed,
    tooltip: describe(s, `${gridName ? `${gridName} · ` : ''}${windowName(window)}`),
  }));
  if (comparative) detailRows.sort((a, b) => (b.observed ?? -Infinity) - (a.observed ?? -Infinity));
  // The reference of the selected grid and window: with several grids, each has its own.
  const reference = detail.find(({ s }) => s.reference)?.s.reference ?? ofTest.find((s) => s.reference)?.reference;
  // A T-test on a single target event has no confidence interval (pyCSEP writes NaN).
  const noIntervals = comparative && detailRows.length > 0 && detailRows.every((r) => r.lower === null);

  const where = `${gridName ? `${gridName}, ` : ''}${windowName(window)}`;
  const xName =
    kind === 'number'
      ? 'Number of events'
      : comparative
        ? `Information gain per earthquake against ${reference ?? 'the reference'}`
        : 'Log-likelihood';
  const heatLegend = (cells: HeatCell[]) => {
    const s = scale(cells.map((c) => c.value));
    return s.kind === 'score' ? (
      <ScoreLegend threshold={s.threshold} label={scoreName} />
    ) : (
      <DivergingLegend limit={s.limit} label="Information gain" />
    );
  };

  const summaryTable = (
    cells: HeatCell[],
    rowsLabel: string[],
    colsLabel: string[],
    colHeader: string,
    caption: string,
  ) => (
    <DataTable
      caption={caption}
      columns={[
        { key: 'model', header: 'Model', render: (c: HeatCell) => rowsLabel[c.row] },
        { key: 'col', header: colHeader, render: (c: HeatCell) => colsLabel[c.col] },
        {
          key: 'v',
          header: comparative ? 'Information gain' : scoreName,
          align: 'right',
          numeric: true,
          sortValue: (c: HeatCell) => c.value ?? -Infinity,
          render: (c: HeatCell) => c.label,
          csv: (c: HeatCell) => c.value,
        },
        {
          key: 'verdict',
          header: 'Outcome',
          sortValue: (c: HeatCell) => (c.passed === null ? 1 : c.passed ? 2 : 0),
          render: (c: HeatCell) =>
            comparative
              ? c.passed === true
                ? 'Better'
                : c.passed === false
                  ? 'Worse'
                  : 'Not different'
              : c.passed === false
                ? 'Rejected'
                : 'Not rejected',
        },
      ]}
      rows={cells}
      rowKey={(c) => `${c.row}-${c.col}`}
      pageSize={12}
    />
  );

  const windowColumns = gridWindows.map(windowName);
  const gridColumns = grids ? shortGridNames(grids.grids, gridSizes) : [];

  return (
    <>
      <FilterBar>
        <Select
          label="Test"
          className="w-full sm:w-60"
          value={test}
          onChange={(value) => set({ test: value })}
          options={tests.map((t) => ({ value: t, label: t }))}
        />
        <Select
          label="Time window"
          className="w-full sm:w-72"
          value={String(windowIndex)}
          onChange={(value) => set({ window: Number(value) + 1 })}
          options={windows.map((w) => ({
            value: String(w.index),
            label: `${windowName(w)} · ${formatDate(w.start)} → ${formatDate(w.end)}`,
            disabled: !windowsWithResults.includes(w),
          }))}
        />
        {grids && gridName && (
          <Select
            label="Grid"
            className="w-full sm:w-40"
            value={gridName}
            onChange={(value) => set({ grid: value })}
            options={grids.grids.map((g) => ({ value: g, label: gridLabel(g, gridSizes) }))}
          />
        )}
      </FilterBar>

      {kind === 'sequential' || kind === 'other' ? (
        <Card>
          <EmptyState
            icon={ChartColumnBig}
            title="Shown as a figure"
            description={`${test} results are not charted here; see its figures in the Figures view.`}
          />
        </Card>
      ) : (
        <div className="flex flex-col gap-5">
          {grids && (
            <ChartCard
              title={`${test} by model and grid`}
              description={`${windowName(window)} · click a cell to show that grid below`}
              table={summaryTable(
                gridCells,
                rowModels,
                gridColumns,
                'Grid',
                `${test} by model and grid, ${windowName(window)}`,
              )}
              footer={heatLegend(gridCells)}
            >
              <EvaluationHeatmap
                rows={rowModels}
                columns={gridColumns}
                cells={gridCells}
                scale={scale(gridCells.map((c) => c.value))}
                xName="Evaluation grid"
                ariaLabel={`${test} results for each model and grid`}
                selected={gridName ? { row: -1, col: grids.grids.indexOf(gridName) } : null}
                onSelect={(_, col) => set({ grid: grids.grids[col] })}
              />
            </ChartCard>
          )}

          <div className="grid gap-5 2xl:grid-cols-2">
            {gridWindows.length > 1 && (
              <ChartCard
                title={`${test} by model and time window`}
                description={`${gridName ? `Grid ${gridName} · ` : ''}click a cell to show that window`}
                table={summaryTable(
                  timeCells,
                  rowModels,
                  windowColumns,
                  'Window',
                  `${test} by model and time window${gridName ? `, ${gridName}` : ''}`,
                )}
                footer={heatLegend(timeCells)}
              >
                <EvaluationHeatmap
                  rows={rowModels}
                  columns={windowColumns}
                  cells={timeCells}
                  scale={scale(timeCells.map((c) => c.value))}
                  ariaLabel={`${test} results for each model and time window`}
                  selected={{ row: -1, col: gridWindows.findIndex((w) => w.index === windowIndex) }}
                  onSelect={(_, col) => set({ window: gridWindows[col].index + 1 })}
                />
              </ChartCard>
            )}

            <ChartCard
              title={comparative ? `Information gain · ${where}` : `${test} · ${where}`}
              description={
                comparative
                  ? noIntervals
                    ? `Per earthquake against ${reference ?? 'the reference'} · no 95% intervals: too few target events`
                    : `Per earthquake against ${reference ?? 'the reference'}, with 95% intervals · best first`
                  : kind === 'number'
                    ? 'Observed number of events against the 95% range of the forecast (Poisson)'
                    : 'Observed statistic against the simulated distribution (5th percentile to maximum)'
              }
              className={gridWindows.length > 1 ? undefined : '2xl:col-span-2'}
              table={
                <DataTable
                  caption={`${test} for ${where}`}
                  columns={[
                    { key: 'model', header: 'Model', render: (r: IntervalRow) => r.label },
                    {
                      key: 'obs',
                      header: comparative ? 'Information gain' : 'Observed',
                      align: 'right',
                      numeric: true,
                      sortValue: (r: IntervalRow) => r.observed ?? -Infinity,
                      render: (r: IntervalRow) => fmt(r.observed, comparative ? 3 : 2),
                      csv: (r: IntervalRow) => r.observed,
                    },
                    {
                      key: 'lo',
                      header: comparative ? 'Lower 95%' : 'Lower',
                      align: 'right',
                      numeric: true,
                      render: (r: IntervalRow) => fmt(r.lower, comparative ? 3 : 2),
                      csv: (r: IntervalRow) => r.lower,
                    },
                    {
                      key: 'hi',
                      header: comparative ? 'Upper 95%' : 'Upper',
                      align: 'right',
                      numeric: true,
                      render: (r: IntervalRow) => fmt(r.upper, comparative ? 3 : 2),
                      csv: (r: IntervalRow) => r.upper,
                    },
                    {
                      key: 'verdict',
                      header: 'Outcome',
                      render: (r: IntervalRow) =>
                        comparative
                          ? r.passed === true
                            ? 'Better'
                            : r.passed === false
                              ? 'Worse'
                              : 'Not different'
                          : r.passed === false
                            ? 'Rejected'
                            : 'Not rejected',
                    },
                  ]}
                  rows={detailRows}
                  rowKey={(r) => r.label}
                />
              }
            >
              {detailRows.length > 0 ? (
                <IntervalChart
                  rows={detailRows}
                  kind={comparative ? 'comparative' : 'consistency'}
                  xName={xName}
                  ariaLabel={`${test} results for ${where}`}
                />
              ) : (
                <p className="py-12 text-center text-xs text-ink-3">
                  No results for this window{gridName ? ' and grid' : ''}.
                </p>
              )}
            </ChartCard>
          </div>
        </div>
      )}
    </>
  );
}
