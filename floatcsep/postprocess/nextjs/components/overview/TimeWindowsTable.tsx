'use client';

import { DataTable, type Column } from '@/components/ui/DataTable';
import { formatInt } from '@/lib/format';
import { formatDate, formatDuration, type TimeWindow } from '@/lib/time';

interface TimeWindowsTableProps {
  windows: TimeWindow[];
  counts?: number[] | null;
  onRowClick?: (window: TimeWindow) => void;
  selected?: number | null;
}

export function TimeWindowsTable({ windows, counts, onRowClick, selected }: TimeWindowsTableProps) {
  const columns: Column<TimeWindow>[] = [
    { key: 'label', header: 'Window', sortValue: (w) => w.index, render: (w) => <span className="font-medium">{w.label}</span> },
    { key: 'start', header: 'Start (UTC)', numeric: true, sortValue: (w) => w.start, render: (w) => formatDate(w.start) },
    { key: 'end', header: 'End (UTC)', numeric: true, sortValue: (w) => w.end, render: (w) => formatDate(w.end) },
    { key: 'duration', header: 'Duration', sortValue: (w) => w.end - w.start, render: (w) => formatDuration(w.end - w.start) },
  ];
  if (counts) {
    columns.push({
      key: 'events',
      header: 'Observed events',
      align: 'right',
      numeric: true,
      sortValue: (w) => counts[w.index] ?? 0,
      render: (w) => formatInt(counts[w.index] ?? 0),
    });
  }
  return (
    <DataTable
      caption="Forecast time windows"
      columns={columns}
      rows={windows}
      rowKey={(w) => w.label}
      onRowClick={onRowClick}
      isRowSelected={selected !== undefined && selected !== null ? (w) => w.index === selected : undefined}
    />
  );
}
