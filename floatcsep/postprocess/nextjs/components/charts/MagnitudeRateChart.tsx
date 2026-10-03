'use client';

import { useMemo } from 'react';
import type { ChartOption } from '@/lib/echarts';
import { formatInt, formatPowerOfTen, formatRate, magnitudeBinLabel, magnitudeDecimals } from '@/lib/format';
import EChart from './EChart';
import { tooltipRow, tooltipTitle, useChartTheme } from './chartTheme';

interface MagnitudeRateChartProps {
  magnitudes: number[];
  expected: number[];
  /** Observed events per magnitude bin, if the catalog is available. */
  observed: number[] | null;
  height?: number;
}

/** Expected (forecast) vs observed number of events per magnitude bin, log scale. */
export default function MagnitudeRateChart({ magnitudes, expected, observed, height = 260 }: MagnitudeRateChartProps) {
  const theme = useChartTheme();

  const option = useMemo<ChartOption>(() => {
    const [expColor, obsColor] = theme.series;
    const decimals = magnitudeDecimals(magnitudes);
    const positive = (v: number) => (v > 0 ? v : null);
    const n = magnitudes.length;
    // Bins are labelled by their lower edge; the last one is open-ended (all larger
    // magnitudes), which is why its expected count can rise. Labels are thinned from the
    // last bin backwards, so that it is always labelled.
    const labels = magnitudes.map((m, k) => (k === n - 1 && n > 1 ? `≥${m.toFixed(decimals)}` : m.toFixed(decimals)));
    const step = Math.max(1, Math.ceil(n / 8));
    const legend = [{ name: 'Expected', icon: 'path://M0,4 L14,4 L14,6 L0,6 Z', itemStyle: { color: expColor } }];
    if (observed) legend.push({ name: 'Observed', icon: 'circle', itemStyle: { color: obsColor } });
    return {
      ...theme.base,
      grid: { left: 8, right: 16, top: 36, bottom: 36 },
      legend: { top: 0, left: 4, itemGap: 18, textStyle: { color: theme.chrome.ink2, fontSize: 12 }, data: legend },
      xAxis: {
        type: 'category',
        data: labels,
        name: 'Magnitude bin',
        nameLocation: 'middle',
        nameGap: 26,
        ...theme.axis({
          splitLine: { show: false },
          axisTick: { alignWithLabel: true, lineStyle: { color: theme.chrome.axis } },
          axisLabel: { color: theme.chrome.muted, fontSize: 11, interval: (k: number) => (n - 1 - k) % step === 0 },
        }),
      },
      yAxis: {
        type: 'log',
        logBase: 10,
        name: 'Events',
        nameLocation: 'middle',
        nameGap: 40,
        ...theme.axis({ axisLabel: { color: theme.chrome.muted, fontSize: 11, formatter: formatPowerOfTen } }),
      },
      tooltip: {
        ...(theme.base.tooltip as object),
        trigger: 'axis',
        axisPointer: { type: 'line', lineStyle: { color: theme.chrome.axis, width: 1 } },
        formatter: (params: any[]) => {
          const k = params[0]?.dataIndex ?? 0;
          const rows = [
            tooltipTitle(`M ${magnitudeBinLabel(magnitudes, k, decimals)}`),
            tooltipRow(expColor, formatRate(expected[k]), 'expected'),
          ];
          if (observed) rows.push(tooltipRow(obsColor, formatInt(observed[k]), 'observed'));
          return rows.join('');
        },
      },
      series: [
        {
          // A line, not bars: log-axis bars would grow from 1, misdrawing rates below 1.
          type: 'line',
          name: 'Expected',
          data: expected.map(positive),
          symbol: 'circle',
          symbolSize: 7,
          showSymbol: magnitudes.length <= 30,
          connectNulls: false,
          lineStyle: { color: expColor, width: 2, cap: 'round', join: 'round' },
          itemStyle: { color: expColor, borderColor: theme.chrome.surface, borderWidth: 2 },
        },
        ...(observed
          ? [
              {
                type: 'scatter',
                name: 'Observed',
                data: observed.map(positive),
                symbolSize: 9,
                itemStyle: { color: obsColor, borderColor: theme.chrome.surface, borderWidth: 2 },
                z: 3,
              },
            ]
          : []),
      ],
    };
  }, [theme, magnitudes, expected, observed]);

  return (
    <EChart option={option} height={height} ariaLabel="Expected and observed number of events per magnitude bin" />
  );
}
