import { LoaderCircle, TriangleAlert, type LucideIcon } from 'lucide-react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';
import { Button } from './Button';

export function Skeleton({ className }: { className?: string }) {
  return (
    <div aria-hidden className={cn('relative overflow-hidden rounded-md bg-surface-2', className)}>
      <div className="absolute inset-0 -translate-x-full animate-shimmer bg-gradient-to-r from-transparent via-surface-3/60 to-transparent" />
    </div>
  );
}

interface LoadingStateProps {
  title?: string;
  description?: ReactNode;
  className?: string;
}

export function LoadingState({ title = 'Loading…', description, className }: LoadingStateProps) {
  return (
    <div
      role="status"
      className={cn('flex flex-col items-center justify-center gap-3 px-6 py-12 text-center', className)}
    >
      <LoaderCircle className="size-5 animate-spin text-ink-3" aria-hidden />
      <div>
        <p className="text-[0.8rem] font-medium text-ink">{title}</p>
        {description && <p className="mt-1 max-w-md text-xs text-ink-3">{description}</p>}
      </div>
    </div>
  );
}

interface ErrorStateProps {
  title: string;
  message?: ReactNode;
  details?: string;
  onRetry?: () => void;
  className?: string;
}

export function ErrorState({ title, message, details, onRetry, className }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className={cn('flex flex-col items-center justify-center gap-3 px-6 py-12 text-center', className)}
    >
      <span className="flex size-9 items-center justify-center rounded-full bg-critical/10 text-critical">
        <TriangleAlert className="size-[18px]" aria-hidden />
      </span>
      <div className="max-w-lg">
        <p className="text-[0.84rem] font-semibold text-ink">{title}</p>
        {message && <p className="mt-1 text-xs leading-5 text-ink-2">{message}</p>}
        {details && (
          <details className="mt-3 text-left">
            <summary className="cursor-pointer text-xs text-ink-3 hover:text-ink">Technical details</summary>
            <pre className="scrollbar-thin mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border bg-surface-2 p-3 text-2xs leading-4 text-ink-2">
              {details}
            </pre>
          </details>
        )}
      </div>
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Try again
        </Button>
      )}
    </div>
  );
}

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ icon: Icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center gap-3 px-6 py-12 text-center', className)}>
      <span className="flex size-9 items-center justify-center rounded-full bg-surface-2 text-ink-3">
        <Icon className="size-[18px]" aria-hidden />
      </span>
      <div className="max-w-md">
        <p className="text-[0.84rem] font-semibold text-ink">{title}</p>
        {description && <p className="mt-1 text-xs leading-5 text-ink-3">{description}</p>}
      </div>
      {action}
    </div>
  );
}
