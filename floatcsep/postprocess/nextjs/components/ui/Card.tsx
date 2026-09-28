import type { HTMLAttributes, ReactNode } from 'react';
import { cn } from '@/lib/utils';

export function Card({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return <section className={cn('min-w-0 rounded-xl border bg-surface shadow-card', className)} {...props} />;
}

interface CardHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
  /** id for the title, to label the card region. */
  id?: string;
}

export function CardHeader({ title, description, actions, className, id }: CardHeaderProps) {
  return (
    <header
      className={cn(
        'flex flex-wrap items-start justify-between gap-x-4 gap-y-2 border-b px-5 py-3.5 sm:flex-nowrap',
        className,
      )}
    >
      <div className="min-w-[min(100%,15rem)] flex-1">
        <h2 id={id} className="text-[0.84rem] font-semibold leading-6 text-ink">
          {title}
        </h2>
        {description && <p className="text-xs leading-5 text-ink-3">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn('p-5', className)} {...props} />;
}
