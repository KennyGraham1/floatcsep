'use client';

import { useEffect, useRef } from 'react';
import { echarts, type ChartOption } from '@/lib/echarts';
import { cn } from '@/lib/utils';

type Handler = (params: any) => void;

interface EChartProps {
  option: ChartOption;
  height: number;
  /** Accessible description of what the chart shows. */
  ariaLabel: string;
  className?: string;
  onEvents?: Record<string, Handler>;
}

/** A resizable Apache ECharts instance that re-renders whenever `option` changes. */
export default function EChart({ option, height, ariaLabel, className, onEvents }: EChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const chart = echarts.init(container, null, { renderer: 'canvas' });
    chartRef.current = chart;
    const observer = new ResizeObserver(() => chart.resize());
    observer.observe(container);
    return () => {
      observer.disconnect();
      chart.dispose();
      chartRef.current = null;
    };
  }, []);

  useEffect(() => {
    chartRef.current?.setOption(option, { notMerge: true, lazyUpdate: true });
  }, [option]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !onEvents) return;
    for (const [name, handler] of Object.entries(onEvents)) chart.on(name, handler);
    return () => {
      for (const [name, handler] of Object.entries(onEvents)) chart.off(name, handler);
    };
  }, [onEvents]);

  return (
    <div ref={containerRef} role="img" aria-label={ariaLabel} className={cn('w-full', className)} style={{ height }} />
  );
}
