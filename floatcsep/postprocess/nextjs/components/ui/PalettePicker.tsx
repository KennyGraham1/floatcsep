'use client';

import { useId } from 'react';
import { useThemeMode } from '@/hooks/useThemeMode';
import { PALETTE_LABELS, PALETTE_NAMES, paletteStops, rampGradient, type PaletteName } from '@/lib/colors';
import { cn } from '@/lib/utils';

interface PalettePickerProps {
  value: PaletteName;
  onChange: (value: PaletteName) => void;
  className?: string;
}

/** Colour palettes as gradient swatches, one of which is selected. */
export function PalettePicker({ value, onChange, className }: PalettePickerProps) {
  const mode = useThemeMode();
  const labelId = useId();
  return (
    <div className={className}>
      <div className="mb-1.5 flex items-baseline justify-between text-xs">
        <span id={labelId} className="font-medium text-ink-2">
          Palette
        </span>
        <span className="text-ink-3">{PALETTE_LABELS[value]}</span>
      </div>
      <div role="radiogroup" aria-labelledby={labelId} className="grid grid-cols-4 gap-2 sm:grid-cols-7 xl:grid-cols-4">
        {PALETTE_NAMES.map((name) => {
          const selected = name === value;
          return (
            <button
              key={name}
              type="button"
              role="radio"
              aria-checked={selected}
              aria-label={PALETTE_LABELS[name]}
              title={PALETTE_LABELS[name]}
              onClick={() => onChange(name)}
              className={cn(
                'h-6 rounded-md ring-1 ring-line transition-shadow focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus',
                selected && 'ring-2 ring-ink ring-offset-2 ring-offset-surface',
              )}
              style={{ background: rampGradient(paletteStops(name, mode)) }}
            />
          );
        })}
      </div>
    </div>
  );
}
