'use client';

import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download } from 'lucide-react';
import { useMemo, useState, type ReactNode } from 'react';
import { downloadText, fileSlug, textOf, toCsv } from '@/lib/csv';
import { formatInt } from '@/lib/format';
import { cn } from '@/lib/utils';
import { Button } from './Button';

export interface Column<T> {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
  /** Enables sorting on this column. */
  sortValue?: (row: T) => number | string;
  align?: 'left' | 'right';
  /** Numeric columns get tabular figures. */
  numeric?: boolean;
  className?: string;
  /** The value in CSV downloads (default: the text of the cell), e.g. an unrounded number. */
  csv?: (row: T) => string | number | null;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T, index: number) => string;
  caption: string;
  pageSize?: number;
  initialSort?: { key: string; direction: 'asc' | 'desc' };
  empty?: ReactNode;
  className?: string;
  onRowClick?: (row: T) => void;
  isRowSelected?: (row: T) => boolean;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  caption,
  pageSize = 10,
  initialSort,
  empty = 'No rows',
  className,
  onRowClick,
  isRowSelected,
}: DataTableProps<T>) {
  const [sort, setSort] = useState(initialSort ?? null);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    const column = sort && columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    const factor = sort!.direction === 'asc' ? 1 : -1;
    const value = column.sortValue;
    return [...rows].sort((a, b) => {
      const va = value(a);
      const vb = value(b);
      return (va < vb ? -1 : va > vb ? 1 : 0) * factor;
    });
  }, [rows, columns, sort]);

  const pageCount = Math.max(1, Math.ceil(sorted.length / pageSize));
  const current = Math.min(page, pageCount - 1);
  const visible = sorted.slice(current * pageSize, (current + 1) * pageSize);

  const downloadCsv = () => {
    const header = columns.map((c) => c.header);
    const body = sorted.map((row) =>
      columns.map((c) => {
        const value = c.csv ? c.csv(row) : textOf(c.render(row));
        return value === null || value === undefined ? '' : String(value);
      }),
    );
    downloadText(`${fileSlug(caption)}.csv`, toCsv(header, body));
  };

  const toggleSort = (key: string) => {
    setPage(0);
    setSort((prev) =>
      prev?.key === key ? { key, direction: prev.direction === 'asc' ? 'desc' : 'asc' } : { key, direction: 'desc' },
    );
  };

  return (
    <div className={cn('min-w-0', className)}>
      <div className="scrollbar-thin overflow-x-auto">
        <table className="w-full border-collapse text-left text-[0.8rem]">
          <caption className="sr-only">{caption}</caption>
          <thead>
            <tr className="border-b">
              {columns.map((column) => {
                const active = sort?.key === column.key;
                const ariaSort = active ? (sort!.direction === 'asc' ? 'ascending' : 'descending') : undefined;
                return (
                  <th
                    key={column.key}
                    scope="col"
                    aria-sort={ariaSort}
                    className={cn(
                      'whitespace-nowrap bg-surface-2/60 px-4 py-2 text-xs font-medium text-ink-3 first:pl-5 last:pr-5',
                      column.align === 'right' && 'text-right',
                    )}
                  >
                    {column.sortValue ? (
                      <button
                        type="button"
                        onClick={() => toggleSort(column.key)}
                        className={cn(
                          'inline-flex items-center gap-1 rounded hover:text-ink',
                          active && 'text-ink',
                          column.align === 'right' && 'flex-row-reverse',
                        )}
                      >
                        {column.header}
                        {active &&
                          (sort!.direction === 'asc' ? (
                            <ArrowUp className="size-3" aria-hidden />
                          ) : (
                            <ArrowDown className="size-3" aria-hidden />
                          ))}
                      </button>
                    ) : (
                      column.header
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {visible.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-5 py-8 text-center text-xs text-ink-3">
                  {empty}
                </td>
              </tr>
            ) : (
              visible.map((row, i) => {
                const selected = isRowSelected?.(row) ?? false;
                return (
                  <tr
                    key={rowKey(row, current * pageSize + i)}
                    onClick={onRowClick ? () => onRowClick(row) : undefined}
                    className={cn(
                      'border-b last:border-b-0',
                      onRowClick && 'cursor-pointer hover:bg-surface-2/70',
                      selected && 'bg-focus/[0.07] hover:bg-focus/10',
                    )}
                  >
                    {columns.map((column) => (
                      <td
                        key={column.key}
                        className={cn(
                          'px-4 py-2 align-top text-ink first:pl-5 last:pr-5',
                          column.align === 'right' && 'text-right',
                          column.numeric && 'tabular whitespace-nowrap',
                          column.className,
                        )}
                      >
                        {column.render(row)}
                      </td>
                    ))}
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
      {sorted.length > 0 && (
        <div className="flex items-center justify-between gap-3 border-t px-5 py-2 text-xs text-ink-3">
          <span className="tabular">
            {sorted.length > pageSize
              ? `${formatInt(current * pageSize + 1)}–${formatInt(Math.min(sorted.length, (current + 1) * pageSize))} of ${formatInt(sorted.length)}`
              : `${formatInt(sorted.length)} ${sorted.length === 1 ? 'row' : 'rows'}`}
          </span>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={downloadCsv}
              title={`Download all ${formatInt(sorted.length)} rows as CSV`}
            >
              <Download /> CSV
            </Button>
            {sorted.length > pageSize && (
              <>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Previous page"
                  disabled={current === 0}
                  onClick={() => setPage(current - 1)}
                >
                  <ChevronLeft />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label="Next page"
                  disabled={current >= pageCount - 1}
                  onClick={() => setPage(current + 1)}
                >
                  <ChevronRight />
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
