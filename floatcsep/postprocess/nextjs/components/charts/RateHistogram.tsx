'use client';

import { useMemo } from 'react';
import { rampColor } from '@/lib/colors';
import type { ChartOption } from '@/lib/echarts';
import { formatInt, formatSci } from '@/lib/format';
import EChart from './EChart';
import { tooltipRow, tooltipTitle, useChartTheme } from './chartTheme';

interface RateHistogramProps {
  /** log10 of the positive cell rates. */
  logRates: Float64Array;
  domain: [number, number];
  /** Current colour range (log10), used to colour the bars like the map. */
  range: [number, number];
  /** The map's colour palette, low → high. */
  stops: string[];
  bins?: number;
  height?: number;
}

/** Distribution of cell rates, coloured with the map's colour scale. */
export default function RateHistogram({ logRates, domain, range, stops, bins = 28, height = 150 }: RateHistogramProps) {
  const theme = useChartTheme();

  const histogram = useMemo(() => {
    const [lo, hi] = domain;
    const width = (hi - lo) / bins || 1;
    const counts = new Array<number>(bins).fill(0);
    for (let i = 0; i < logRates.length; i++) {
      if (!Number.isFinite(logRates[i])) continue; // zero rates: no cell drawn, no bar
      const k = Math.min(bins - 1, Math.max(0, Math.floor((logRates[i] - lo) / width)));
      counts[k]++;
    }
    const centers = counts.map((_, k) => lo + (k + 0.5) * width);
    return { counts, centers, width };
  }, [logRates, domain, bins]);

  const option = useMemo<ChartOption>(() => {
    const [cMin, cMax] = range;
    const span = cMax - cMin || 1;
    return {
      ...theme.base,
      grid: { left: 4, right: 4, top: 8, bottom: 22 },
      xAxis: {
        type: 'category',
        data: histogram.centers.map((c) => c.toFixed(2)),
        ...theme.axis({
          splitLine: { show: false },
          axisTick: { show: false },
          axisLabel: { color: theme.chrome.muted, fontSize: 10, interval: Math.ceil(bins / 6) - 1, hideOverlap: true },
        }),
      },
      yAxis: { type: 'value', show: false },
      tooltip: {
        ...(theme.base.tooltip as object),
        trigger: 'item',
        formatter: (params: any) => {
          const k = params.dataIndex;
          const from = domain[0] + k * histogram.width;
          return [
            tooltipTitle(`λ ${formatSci(10 ** from)} – ${formatSci(10 ** (from + histogram.width))}`),
            tooltipRow(null, formatInt(histogram.counts[k]), 'cells'),
          ].join('');
        },
      },
      series: [
        {
          type: 'bar',
          barCategoryGap: '12%',
          data: histogram.counts.map((count, k) => ({
            value: count,
            itemStyle: {
              color: rampColor(stops, (histogram.centers[k] - cMin) / span),
              borderRadius: [2, 2, 0, 0],
            },
          })),
        },
      ],
    };
  }, [theme, histogram, range, stops, domain, bins]);

  return <EChart option={option} height={height} ariaLabel="Histogram of forecast cell rates" />;
}
