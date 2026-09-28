'use client';

import { ImageOff } from 'lucide-react';
import { useState } from 'react';
import { Skeleton } from '@/components/ui/States';
import { cn } from '@/lib/utils';

interface FigureImageProps {
  src: string;
  alt: string;
  onOpen?: () => void;
  className?: string;
  /** Reserve this aspect ratio while loading (width / height). */
  aspect?: number;
}

/** A result figure with loading and error states; click to open it larger. */
export function FigureImage({ src, alt, onOpen, className, aspect = 4 / 3 }: FigureImageProps) {
  const [state, setState] = useState<'loading' | 'loaded' | 'error'>('loading');

  if (state === 'error') {
    return (
      <div
        className={cn('flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-surface-2 text-xs text-ink-3', className)}
        style={{ aspectRatio: aspect }}
      >
        <ImageOff className="size-5" aria-hidden />
        The figure could not be loaded.
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={!onOpen}
      aria-label={onOpen ? `Enlarge: ${alt}` : undefined}
      className={cn(
        'group relative block w-full overflow-hidden rounded-lg border bg-white text-left transition-shadow',
        onOpen && 'cursor-zoom-in hover:shadow-overlay',
        className,
      )}
      style={state === 'loading' ? { aspectRatio: aspect } : undefined}
    >
      {state === 'loading' && <Skeleton className="absolute inset-0 rounded-none" />}
      {/* eslint-disable-next-line @next/next/no-img-element -- local result figure of unknown size */}
      <img
        src={src}
        alt={alt}
        decoding="async"
        onLoad={() => setState('loaded')}
        onError={() => setState('error')}
        className={cn('mx-auto block h-auto max-w-full', state === 'loading' && 'opacity-0')}
      />
    </button>
  );
}
