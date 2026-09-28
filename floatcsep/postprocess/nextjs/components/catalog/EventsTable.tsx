'use client';

import { useMemo } from 'react';
import { DataTable, type Column } from '@/components/ui/DataTable';
import { LegendDot } from '@/components/maps/MapOverlays';
import { useThemeMode } from '@/hooks/useThemeMode';
import { INPUT, type Catalog } from '@/lib/catalog';
import { EVENT_COLORS } from '@/lib/colors';
import { formatLatLon, formatMagnitude } from '@/lib/format';
import { formatDateTime } from '@/lib/time';

interface EventsTableProps {
  catalog: Catalog;
  indices: ArrayLike<number>;
  pageSize?: number;
  caption: string;
  /** Show only the N largest events. */
  limit?: number;
  /** Fewer columns for narrow cards: the period becomes a dot beside the magnitude. */
  compact?: boolean;
}

export function EventsTable({ catalog, indices, pageSize = 10, caption, limit, compact = false }: EventsTableProps) {
  const mode = useThemeMode();
  const colors = EVENT_COLORS[mode];

  const rows = useMemo(() => {
    const all = Array.from(indices);
    if (!limit) return all;
    return all.sort((a, b) => catalog.mag[b] - catalog.mag[a]).slice(0, limit);
  }, [catalog, indices, limit]);

  const dot = (i: number) => <LegendDot color={catalog.kind[i] === INPUT ? colors.input : colors.test} size={8} />;

  const all: Column<number>[] = [
    {
      key: 'mag',
      header: 'Magnitude',
      numeric: true,
      sortValue: (i) => catalog.mag[i],
      render: (i) =>
        compact ? (
          <span
            className="inline-flex items-center gap-2 font-medium"
            title={catalog.kind[i] === INPUT ? 'Before the experiment start' : 'Experiment period'}
          >
            {dot(i)}
            {formatMagnitude(catalog.mag[i])}
          </span>
        ) : (
          <span className="font-medium">{formatMagnitude(catalog.mag[i])}</span>
        ),
    },
    {
      key: 'time',
      header: 'Origin time (UTC)',
      numeric: true,
      sortValue: (i) => catalog.time[i],
      render: (i) => formatDateTime(catalog.time[i]),
    },
    {
      key: 'location',
      header: 'Location',
      numeric: true,
      render: (i) => formatLatLon(catalog.lat[i], catalog.lon[i]),
    },
    {
      key: 'depth',
      header: 'Depth',
      align: 'right',
      numeric: true,
      sortValue: (i) => (Number.isFinite(catalog.depth[i]) ? catalog.depth[i] : -1),
      render: (i) => (Number.isFinite(catalog.depth[i]) ? `${catalog.depth[i].toFixed(1)} km` : '—'),
    },
    {
      key: 'class',
      header: 'Period',
      sortValue: (i) => catalog.kind[i],
      render: (i) => (
        <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-xs text-ink-2">
          {dot(i)}
          {catalog.kind[i] === INPUT ? 'Before start' : 'Experiment'}
        </span>
      ),
    },
    {
      key: 'id',
      header: 'Event ID',
      render: (i) => <code className="text-xs text-ink-2">{catalog.id[i]}</code>,
    },
  ];
  const columns = compact ? all.filter((c) => c.key !== 'class' && c.key !== 'id') : all;

  return (
    <DataTable
      caption={caption}
      columns={columns}
      rows={rows}
      rowKey={(i) => String(i)}
      pageSize={pageSize}
      initialSort={{ key: 'mag', direction: 'desc' }}
      empty="No events match the filters."
    />
  );
}
