'use client';

import { ChevronLeft, ChevronRight, Download, ExternalLink, X } from 'lucide-react';
import { useEffect, useRef } from 'react';
import { Button, LinkButton } from './Button';

export interface LightboxItem {
  src: string;
  title: string;
  subtitle?: string;
  downloadHref: string;
}

interface LightboxProps {
  items: LightboxItem[];
  index: number | null;
  onIndexChange: (index: number | null) => void;
}

/** Full-screen figure viewer on a native <dialog> (focus trap and Esc built in). */
export function Lightbox({ items, index, onIndexChange }: LightboxProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const item = index !== null ? items[index] : null;

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (item && !dialog.open) dialog.showModal();
    if (!item && dialog.open) dialog.close();
  }, [item]);

  const step = (delta: number) => {
    if (index === null || items.length < 2) return;
    onIndexChange((index + delta + items.length) % items.length);
  };

  return (
    <dialog
      ref={dialogRef}
      onClose={() => onIndexChange(null)}
      onKeyDown={(event) => {
        if (event.key === 'ArrowRight') step(1);
        if (event.key === 'ArrowLeft') step(-1);
      }}
      onClick={(event) => {
        if (event.target === dialogRef.current) onIndexChange(null);
      }}
      aria-label={item?.title ?? 'Figure viewer'}
      className="m-0 h-full max-h-none w-full max-w-none bg-transparent p-0 backdrop:bg-black/75 backdrop:backdrop-blur-[2px]"
    >
      {item && (
        <div className="flex h-full flex-col" onClick={(e) => e.target === e.currentTarget && onIndexChange(null)}>
          <div className="flex items-center justify-between gap-3 border-b border-white/10 bg-black/60 px-4 py-2.5 text-white">
            <div className="min-w-0">
              <p className="truncate text-[0.84rem] font-semibold">{item.title}</p>
              {item.subtitle && <p className="truncate text-xs text-white/65">{item.subtitle}</p>}
            </div>
            <div className="flex shrink-0 items-center gap-1.5">
              {items.length > 1 && (
                <span className="mr-2 text-xs tabular text-white/65">
                  {index! + 1} / {items.length}
                </span>
              )}
              <LinkButton
                href={item.src}
                target="_blank"
                rel="noopener noreferrer"
                variant="ghost"
                size="sm"
                className="text-white hover:bg-white/10 hover:text-white"
              >
                <ExternalLink /> Open
              </LinkButton>
              <LinkButton
                href={item.downloadHref}
                variant="ghost"
                size="sm"
                className="text-white hover:bg-white/10 hover:text-white"
              >
                <Download /> Download
              </LinkButton>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Close"
                autoFocus
                onClick={() => onIndexChange(null)}
                className="text-white hover:bg-white/10 hover:text-white"
              >
                <X />
              </Button>
            </div>
          </div>
          <div
            className="relative flex min-h-0 flex-1 items-center justify-center p-4 sm:p-8"
            onClick={(e) => e.target === e.currentTarget && onIndexChange(null)}
          >
            {/* eslint-disable-next-line @next/next/no-img-element -- local result figure of unknown size */}
            <img
              src={item.src}
              alt={item.title}
              className="max-h-full max-w-full rounded-md bg-white object-contain shadow-overlay"
            />
            {items.length > 1 && (
              <>
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label="Previous figure"
                  onClick={() => step(-1)}
                  className="absolute left-3 top-1/2 size-10 -translate-y-1/2 rounded-full"
                >
                  <ChevronLeft />
                </Button>
                <Button
                  variant="secondary"
                  size="icon"
                  aria-label="Next figure"
                  onClick={() => step(1)}
                  className="absolute right-3 top-1/2 size-10 -translate-y-1/2 rounded-full"
                >
                  <ChevronRight />
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </dialog>
  );
}
