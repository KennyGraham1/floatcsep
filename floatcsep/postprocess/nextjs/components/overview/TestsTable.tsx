'use client';

import { DataTable, type Column } from '@/components/ui/DataTable';
import type { Manifest, Test } from '@/lib/types';

/** "csep.core.poisson_evaluations.number_test" -> "poisson_evaluations.number_test" */
export function shortFunctionName(name: string | null): string | null {
  if (!name) return null;
  return name.replace(/^csep\.core\./, '').replace(/^csep\.utils\./, '').replace(/^floatcsep\.utils\./, '');
}

export function TestsTable({ manifest }: { manifest: Manifest }) {
  const figures = new Map<string, number>();
  for (const figure of manifest.results) figures.set(figure.test, (figures.get(figure.test) ?? 0) + 1);

  const columns: Column<Test>[] = [
    {
      key: 'name',
      header: 'Test',
      sortValue: (t) => t.name.toLowerCase(),
      render: (t) => <span className="font-medium">{t.name}</span>,
    },
    {
      key: 'func',
      header: 'Evaluation function',
      render: (t) =>
        t.func ? (
          <code className="text-xs text-ink-2" title={t.func}>
            {shortFunctionName(t.func)}
          </code>
        ) : (
          <span className="text-ink-3">—</span>
        ),
    },
    {
      key: 'ref',
      header: 'Reference model',
      render: (t) => t.ref_model ?? <span className="text-ink-3">—</span>,
    },
    {
      key: 'plots',
      header: 'Plots',
      render: (t) =>
        t.plot_func.length > 0 ? (
          <span className="text-xs text-ink-2">{t.plot_func.map((f) => f.split('.').pop()).join(', ')}</span>
        ) : (
          <span className="text-ink-3">—</span>
        ),
    },
    {
      key: 'figures',
      header: 'Figures',
      align: 'right',
      numeric: true,
      sortValue: (t) => figures.get(t.name) ?? 0,
      render: (t) => figures.get(t.name) ?? 0,
    },
  ];

  return (
    <DataTable
      caption="Evaluation tests of the experiment"
      columns={columns}
      rows={manifest.tests}
      rowKey={(t) => t.name}
      empty="This experiment has no tests."
    />
  );
}
