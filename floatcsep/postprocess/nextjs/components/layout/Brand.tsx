import { Earth } from 'lucide-react';
import { cn } from '@/lib/utils';

/** floatCSEP wordmark: italic crimson "float" and upright "CSEP", as in the logo. */
export function Brand({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5', className)}>
      <span className="flex size-7 items-center justify-center rounded-lg bg-accent text-white shadow-card dark:text-page">
        <Earth className="size-4" strokeWidth={2.2} aria-hidden />
      </span>
      <span className="text-[1.05rem] leading-none tracking-tight text-ink">
        <span className="font-serif italic text-accent">float</span>
        <span className="font-semibold">CSEP</span>
      </span>
    </span>
  );
}
