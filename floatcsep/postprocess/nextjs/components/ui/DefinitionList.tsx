import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface Definition {
  label: string;
  value: ReactNode;
}

interface DefinitionListProps {
  items: Definition[];
  /** "stacked" puts each label above its value (narrow side panels). */
  layout?: 'columns' | 'stacked';
  className?: string;
}

/** Label/value rows; rows with an empty value are skipped. */
export function DefinitionList({ items, layout = 'columns', className }: DefinitionListProps) {
  const visible = items.filter(
    (item) => item.value !== null && item.value !== undefined && item.value !== '' && item.value !== false,
  );
  return (
    <dl className={cn('divide-y text-[0.8rem]', className)}>
      {visible.map((item) => (
        <div
          key={item.label}
          className={cn(
            'py-2.5 first:pt-0 last:pb-0',
            layout === 'columns' ? 'grid grid-cols-[minmax(7rem,38%)_1fr] gap-4' : 'flex flex-col gap-1',
          )}
        >
          <dt className={layout === 'columns' ? 'text-ink-3' : 'text-xs text-ink-3'}>{item.label}</dt>
          <dd className="min-w-0 break-words text-ink">{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
