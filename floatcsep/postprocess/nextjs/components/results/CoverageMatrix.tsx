'use client';

import type { TimeWindow } from '@/lib/time';
import { cn } from '@/lib/utils';

interface CoverageMatrixProps {
  tests: string[];
  windows: TimeWindow[];
  /** Number of figures per "window|test". */
  counts: Map<string, number>;
  selected: { test: string; window: number };
  onSelect: (test: string, window: number) => void;
}

/**
 * Which test/window combinations have figures; click a cell to open it.
 * Cells shrink to fit the card and scroll horizontally only for many windows.
 */
export function CoverageMatrix({ tests, windows, counts, selected, onSelect }: CoverageMatrixProps) {
  const labelEvery = windows.length > 12 ? Math.ceil(windows.length / 8) : 1;
  const columns = `minmax(4.5rem, 8rem) repeat(${windows.length}, minmax(12px, 1fr))`;

  return (
    <div className="scrollbar-thin overflow-x-auto pb-1">
      <div role="grid" aria-label="Result figures per test and time window" className="grid min-w-min gap-1 pr-3" style={{ gridTemplateColumns: columns }}>
        <div role="row" className="contents">
          {/* The cell must stay in the grid flow; only its text is visually hidden. */}
          <span role="columnheader">
            <span className="sr-only">Test</span>
          </span>
          {windows.map((w) => (
            <span
              key={w.index}
              role="columnheader"
              aria-label={w.label}
              className="whitespace-nowrap text-center text-2xs font-medium text-ink-3"
            >
              {w.index % labelEvery === 0 || w.index === windows.length - 1 ? w.label : ''}
            </span>
          ))}
        </div>
        {tests.map((test) => (
          <div key={test} role="row" className="contents">
            <span role="rowheader" className="truncate pr-1 text-xs leading-5 text-ink-2" title={test}>
              {test}
            </span>
            {windows.map((w) => {
              const n = counts.get(`${w.index}|${test}`) ?? 0;
              const active = selected.test === test && selected.window === w.index;
              return (
                <button
                  key={w.index}
                  type="button"
                  role="gridcell"
                  disabled={n === 0}
                  onClick={() => onSelect(test, w.index)}
                  title={`${test} · ${w.label}: ${n === 0 ? 'no figures' : `${n} figure${n === 1 ? '' : 's'}`}`}
                  aria-label={`${test}, ${w.label}: ${n} figures`}
                  aria-selected={active}
                  className={cn(
                    'h-5 min-w-3 rounded-[4px] transition-colors',
                    n > 0 ? 'bg-focus/70 hover:bg-focus' : 'cursor-default bg-surface-3',
                    active && 'ring-2 ring-ink ring-offset-1 ring-offset-surface',
                  )}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="mt-3 flex items-center gap-4 text-2xs text-ink-3">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-[3px] bg-focus/70" aria-hidden /> Figures available
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block size-2.5 rounded-[3px] bg-surface-3" aria-hidden /> None
        </span>
      </div>
    </div>
  );
}
