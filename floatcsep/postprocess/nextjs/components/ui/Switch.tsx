'use client';

import { cn } from '@/lib/utils';

interface SwitchProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label: string;
  className?: string;
}

export function Switch({ checked, onChange, label, className }: SwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn('group inline-flex items-center gap-2 text-[0.8rem] text-ink-2 hover:text-ink', className)}
    >
      <span
        className={cn(
          'relative inline-flex h-[18px] w-8 shrink-0 items-center rounded-full border transition-colors',
          checked ? 'border-ink bg-ink' : 'border-line-strong bg-surface-3',
        )}
      >
        <span
          className={cn(
            'inline-block size-3 rounded-full bg-surface shadow transition-transform',
            checked ? 'translate-x-[15px]' : 'translate-x-[2px]',
          )}
        />
      </span>
      {label}
    </button>
  );
}
