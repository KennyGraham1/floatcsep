import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface StatTileProps {
  label: string;
  value: ReactNode;
  /** Secondary line under the value (units, context). */
  caption?: ReactNode;
  className?: string;
}

/** A headline number: sentence-case label, value, optional caption. */
export function StatTile({ label, value, caption, className }: StatTileProps) {
  return (
    <div className={cn('min-w-0 rounded-xl border bg-surface px-4 py-3.5 shadow-card', className)}>
      <div className="truncate text-xs font-medium text-ink-3">{label}</div>
      <div className="mt-1 truncate text-[1.4rem] font-semibold leading-8 tracking-tight text-ink">{value}</div>
      {caption && <div className="mt-0.5 truncate text-xs text-ink-3">{caption}</div>}
    </div>
  );
}

export function StatGrid({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6', className)}>{children}</div>;
}
