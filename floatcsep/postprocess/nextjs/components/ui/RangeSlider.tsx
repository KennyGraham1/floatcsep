'use client';

import { cn } from '@/lib/utils';

interface RangeSliderProps {
  min: number;
  max: number;
  step: number;
  value: [number, number];
  onChange: (value: [number, number]) => void;
  label: string;
  formatValue?: (value: number) => string;
  className?: string;
}

/**
 * A two-thumb slider built from two native range inputs, so both thumbs keep
 * native keyboard, touch and screen-reader support.
 */
export function RangeSlider({ min, max, step, value, onChange, label, formatValue = String, className }: RangeSliderProps) {
  const span = max - min || 1;
  const [lo, hi] = value;
  const left = ((lo - min) / span) * 100;
  const right = ((hi - min) / span) * 100;
  const thumb =
    'pointer-events-none absolute inset-x-0 top-1/2 h-5 w-full -translate-y-1/2 appearance-none bg-transparent ' +
    '[&::-webkit-slider-thumb]:pointer-events-auto [&::-webkit-slider-thumb]:size-4 [&::-webkit-slider-thumb]:cursor-grab ' +
    '[&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:border-2 ' +
    '[&::-webkit-slider-thumb]:border-ink [&::-webkit-slider-thumb]:bg-surface [&::-webkit-slider-thumb]:shadow ' +
    '[&::-moz-range-thumb]:pointer-events-auto [&::-moz-range-thumb]:size-3.5 [&::-moz-range-thumb]:cursor-grab ' +
    '[&::-moz-range-thumb]:rounded-full [&::-moz-range-thumb]:border-2 [&::-moz-range-thumb]:border-ink ' +
    '[&::-moz-range-thumb]:bg-surface focus-visible:outline-none ' +
    'focus-visible:[&::-webkit-slider-thumb]:ring-2 focus-visible:[&::-webkit-slider-thumb]:ring-focus ' +
    'focus-visible:[&::-moz-range-thumb]:ring-2 focus-visible:[&::-moz-range-thumb]:ring-focus';

  return (
    <div className={cn('relative h-5', className)}>
      <div className="absolute inset-x-0 top-1/2 h-1 -translate-y-1/2 rounded-full bg-surface-3" />
      <div
        className="absolute top-1/2 h-1 -translate-y-1/2 rounded-full bg-ink/70"
        style={{ left: `${left}%`, width: `${Math.max(0, right - left)}%` }}
      />
      <input
        type="range"
        aria-label={`${label} minimum`}
        aria-valuetext={formatValue(lo)}
        min={min}
        max={max}
        step={step}
        value={lo}
        onChange={(event) => onChange([Math.min(Number(event.target.value), hi - step), hi])}
        className={thumb}
      />
      <input
        type="range"
        aria-label={`${label} maximum`}
        aria-valuetext={formatValue(hi)}
        min={min}
        max={max}
        step={step}
        value={hi}
        onChange={(event) => onChange([lo, Math.max(Number(event.target.value), lo + step)])}
        className={thumb}
      />
    </div>
  );
}
