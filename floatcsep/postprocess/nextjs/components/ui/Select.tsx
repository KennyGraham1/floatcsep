'use client';

import { ChevronDown } from 'lucide-react';
import { useId, type ReactNode } from 'react';
import { cn } from '@/lib/utils';

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

interface SelectProps {
  label: string;
  value: string;
  options: SelectOption[];
  onChange: (value: string) => void;
  className?: string;
  /** Rendered next to the select (e.g. previous/next buttons). */
  addon?: ReactNode;
  hideLabel?: boolean;
}

export function Select({ label, value, options, onChange, className, addon, hideLabel }: SelectProps) {
  const id = useId();
  return (
    <div className={cn('flex min-w-0 flex-col gap-1.5', className)}>
      <label htmlFor={id} className={cn('text-xs font-medium text-ink-2', hideLabel && 'sr-only')}>
        {label}
      </label>
      <div className="flex min-w-0 items-center gap-1.5">
        <div className="relative min-w-0 flex-1">
          <select
            id={id}
            value={value}
            onChange={(event) => onChange(event.target.value)}
            className="h-9 w-full min-w-0 cursor-pointer appearance-none truncate rounded-md border border-line-strong bg-surface pl-3 pr-8 text-[0.8rem] text-ink transition-colors hover:border-ink-3"
          >
            {options.map((option) => (
              <option key={option.value} value={option.value} disabled={option.disabled}>
                {option.label}
              </option>
            ))}
          </select>
          <ChevronDown
            className="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-ink-3"
            aria-hidden
          />
        </div>
        {addon}
      </div>
    </div>
  );
}
