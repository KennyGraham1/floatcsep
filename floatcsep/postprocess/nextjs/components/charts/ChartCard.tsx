'use client';

import { ChartSpline, Table2 } from 'lucide-react';
import { useState, type ReactNode } from 'react';
import { Card, CardHeader } from '@/components/ui/Card';
import ErrorBoundary from '@/components/ui/ErrorBoundary';
import { SegmentedControl } from '@/components/ui/SegmentedControl';
import { cn } from '@/lib/utils';

interface ChartCardProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  /** The chart's table twin: every value is reachable without hovering. */
  table?: ReactNode;
  footer?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function ChartCard({ title, description, actions, table, footer, children, className, bodyClassName }: ChartCardProps) {
  const [view, setView] = useState<'chart' | 'table'>('chart');
  const label = typeof title === 'string' ? title : 'Chart';

  return (
    <Card className={cn('flex flex-col', className)}>
      <CardHeader
        title={title}
        description={description}
        actions={
          (actions || table) && (
            <>
              {actions}
              {table && (
                <SegmentedControl
                  label={`${label} view`}
                  value={view}
                  onChange={setView}
                  options={[
                    { value: 'chart', label: <ChartSpline />, title: 'Show chart' },
                    { value: 'table', label: <Table2 />, title: 'Show table' },
                  ]}
                />
              )}
            </>
          )
        }
      />
      <ErrorBoundary label={label}>
        {view === 'table' && table ? (
          <div className="flex-1">{table}</div>
        ) : (
          <div className={cn('flex-1 px-3 pb-2 pt-3', bodyClassName)}>{children}</div>
        )}
      </ErrorBoundary>
      {footer && <div className="border-t px-5 py-2.5 text-xs text-ink-3">{footer}</div>}
    </Card>
  );
}
