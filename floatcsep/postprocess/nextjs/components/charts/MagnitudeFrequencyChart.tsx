'use client';

import { useMemo } from 'react';
import type { MagnitudeFrequency } from '@/lib/catalog';
import type { ChartOption } from '@/lib/echarts';
import { formatInt, formatPowerOfTen } from '@/lib/format';
import EChart from './EChart';
import { tooltipRow, tooltipTitle, useChartTheme } from './chartTheme';

interface MagnitudeFrequencyChartProps {
  mfd: MagnitudeFrequency;
  binWidth: number;
  height?: number;
}

/** Gutenberg–Richter plot: cumulative N(≥M) as a line, per-bin counts as bars, log scale. */
export default function MagnitudeFrequencyChart({ mfd, binWidth, height = 300 }: MagnitudeFrequencyChartProps) {
  const theme = useChartTheme();

  const option = useMemo<ChartOption>(() => {
    const [cumColor, incColor] = theme.series;
    const labels = mfd.magnitudes.map((m) => m.toFixed(1));
    const positive = (v: number) => (v > 0 ? v : null);
    return {
      ...theme.base,
      grid: { left: 8, right: 16, top: 36, bottom: 36 },
      legend: {
        top: 0,
        left: 4,
        itemGap: 18,
        textStyle: { color: theme.chrome.ink2, fontSize: 12 },
        data: [
          { name: 'Cumulative N(≥M)', icon: 'path://M0,4 L14,4 L14,6 L0,6 Z', itemStyle: { color: cumColor } },
          { name: 'Events per bin', icon: 'roundRect', itemStyle: { color: incColor } },
        ],
      },
      xAxis: {
        type: 'category',
        data: labels,
        name: 'Magnitude',
        nameLocation: 'middle',
        nameGap: 26,
        ...theme.axis({ splitLine: { show: false }, axisTick: { alignWithLabel: true } }),
      },
      yAxis: {
        type: 'log',
        logBase: 10,
        min: 1,
        name: 'Number of events',
        nameLocation: 'middle',
        nameGap: 38,
        ...theme.axis({ axisLabel: { color: theme.chrome.muted, fontSize: 11, formatter: formatPowerOfTen } }),
      },
      tooltip: {
        ...(theme.base.tooltip as object),
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: theme.chrome.axis, width: 1 } },
        formatter: (params: any[]) => {
          const k = params[0]?.dataIndex ?? 0;
          const m = mfd.magnitudes[k];
          return [
            tooltipTitle(`M ${m.toFixed(1)}–${(m + binWidth).toFixed(1)}`),
            tooltipRow(cumColor, formatInt(mfd.cumulative[k]), `events with M ≥ ${m.toFixed(1)}`),
            tooltipRow(incColor, formatInt(mfd.incremental[k]), 'events in bin'),
          ].join('');
        },
      },
      series: [
        {
          type: 'bar',
          name: 'Events per bin',
          data: mfd.incremental.map(positive),
          barMaxWidth: 12,
          barCategoryGap: '45%',
          itemStyle: { color: incColor, opacity: 0.9, borderRadius: [2, 2, 0, 0] },
        },
        {
          type: 'line',
          name: 'Cumulative N(≥M)',
          data: mfd.cumulative.map(positive),
          showSymbol: mfd.magnitudes.length <= 40,
          symbol: 'circle',
          symbolSize: 7,
          lineStyle: { color: cumColor, width: 2, cap: 'round', join: 'round' },
          itemStyle: { color: cumColor, borderColor: theme.chrome.surface, borderWidth: 2 },
          z: 3,
        },
      ],
    };
  }, [theme, mfd, binWidth]);

  return (
    <EChart
      option={option}
      height={height}
      ariaLabel="Magnitude-frequency distribution of the selected events on a logarithmic scale"
    />
  );
}
