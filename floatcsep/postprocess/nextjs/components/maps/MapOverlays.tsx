import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

const POSITIONS = {
  'top-left': 'left-14 top-3',
  // Clear of the attribution line (which wraps to two lines on phones).
  'bottom-left': 'bottom-11 left-3 sm:bottom-7',
  'bottom-right': 'bottom-7 right-3',
} as const;

/** A small panel over the map for legends and readouts. */
export function MapPanel({
  position,
  children,
  className,
  live = false,
}: {
  position: keyof typeof POSITIONS;
  children: ReactNode;
  className?: string;
  /** Announce changes to screen readers (hover readouts). */
  live?: boolean;
}) {
  return (
    <div
      aria-live={live ? 'polite' : undefined}
      className={cn(
        'pointer-events-none absolute z-[900] max-w-[calc(100%-1.5rem)] rounded-lg border bg-surface/95 px-3 py-2 text-xs text-ink shadow-card backdrop-blur',
        POSITIONS[position],
        className,
      )}
    >
      {children}
    </div>
  );
}

export function LegendDot({ color, size = 10 }: { color: string; size?: number }) {
  return (
    <span
      aria-hidden
      className="inline-block shrink-0 rounded-full ring-1 ring-surface"
      style={{ width: size, height: size, background: color }}
    />
  );
}

/** A continuous colour scale with its end values. */
export function ColorScaleLegend({
  title,
  gradient,
  min,
  max,
}: {
  title: ReactNode;
  gradient: string;
  min: string;
  max: string;
}) {
  return (
    <div className="w-52">
      <div className="mb-1.5 font-medium text-ink-2">{title}</div>
      <div className="h-2.5 rounded-sm ring-1 ring-line" style={{ background: gradient }} />
      <div className="mt-1 flex justify-between tabular text-2xs text-ink-3">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}
