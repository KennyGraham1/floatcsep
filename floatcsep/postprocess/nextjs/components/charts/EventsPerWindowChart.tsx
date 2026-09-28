'use client';

import { useMemo } from 'react';
import type { ChartOption } from '@/lib/echarts';
import { formatInt } from '@/lib/format';
import { formatDate, type TimeWindow } from '@/lib/time';
import EChart from './EChart';
import { tooltipRow, tooltipTitle, useChartTheme } from './chartTheme';

interface EventsPerWindowChartProps {
  windows: TimeWindow[];
  counts: number[];
  onSelect?: (windowIndex: number) => void;
  height?: number;
}

/** Observed events per forecast time window (one series, so no legend). */
export default function EventsPerWindowChart({ windows, counts, onSelect, height = 260 }: EventsPerWindowChartProps) {
  const theme = useChartTheme();

  const option = useMemo<ChartOption>(() => {
    const color = theme.series[0];
    return {
      ...theme.base,
      grid: { left: 8, right: 16, top: 16, bottom: 28 },
      xAxis: {
        type: 'category',
        data: windows.map((w) => w.label),
        ...theme.axis({ splitLine: { show: false }, axisTick: { alignWithLabel: true } }),
      },
      yAxis: {
        type: 'value',
        minInterval: 1,
        ...theme.axis(),
      },
      tooltip: {
        ...(theme.base.tooltip as object),
        trigger: 'item',
        formatter: (params: any) => {
          const w = windows[params.dataIndex];
          return [
            tooltipTitle(`${w.label} · ${formatDate(w.start)} → ${formatDate(w.end)}`),
            tooltipRow(color, formatInt(counts[params.dataIndex]), 'events'),
          ].join('');
        },
      },
      series: [
        {
          type: 'bar',
          name: 'Events',
          data: counts,
          barMaxWidth: 24,
          barCategoryGap: '30%',
          cursor: onSelect ? 'pointer' : 'default',
          itemStyle: { color, borderRadius: [4, 4, 0, 0] },
          emphasis: { itemStyle: { color, opacity: 0.8 } },
        },
      ],
    };
  }, [theme, windows, counts, onSelect]);

  const events = useMemo(
    () => (onSelect ? { click: (params: any) => onSelect(params.dataIndex) } : undefined),
    [onSelect],
  );

  return (
    <EChart option={option} height={height} onEvents={events} ariaLabel="Number of observed events in each time window" />
  );
}
