'use client';

import { useMemo } from 'react';
import { INPUT, type Catalog } from '@/lib/catalog';
import type { ChartOption } from '@/lib/echarts';
import { formatLatLon, formatMagnitude } from '@/lib/format';
import { formatDateTime, windowsAreDisjoint, type TimeWindow } from '@/lib/time';
import { extent } from '@/lib/utils';
import EChart from './EChart';
import { TIME_AXIS_LABELS, tooltipRow, tooltipTitle, useChartTheme } from './chartTheme';

interface MagnitudeTimeChartProps {
  catalog: Catalog;
  indices: Uint32Array;
  windows: TimeWindow[];
  startMs: number;
  /** Visible time range; null shows everything. */
  zoom: [number, number] | null;
  height?: number;
}

const MAX_BANDS = 200;

export default function MagnitudeTimeChart({
  catalog,
  indices,
  windows,
  startMs,
  zoom,
  height = 360,
}: MagnitudeTimeChartProps) {
  const theme = useChartTheme();

  const option = useMemo<ChartOption>(() => {
    const input: number[][] = [];
    const test: number[][] = [];
    for (let j = 0; j < indices.length; j++) {
      const i = indices[j];
      (catalog.kind[i] === INPUT ? input : test).push([catalog.time[i], catalog.mag[i], i]);
    }
    const magRange = extent(Array.from(indices, (i) => catalog.mag[i])) ?? [0, 1];
    const large = indices.length > 5000;
    const point = (color: string) => ({
      symbolSize: large ? 6 : 8,
      large,
      largeThreshold: 5000,
      itemStyle: { color, opacity: 0.85, borderColor: theme.chrome.surface, borderWidth: large ? 0 : 1 },
      emphasis: { scale: 1.6, itemStyle: { opacity: 1 } },
    });

    // Alternate shading only reads for back-to-back windows, not cumulative ones.
    const bands =
      windows.length <= MAX_BANDS && windowsAreDisjoint(windows)
        ? windows.filter((w) => w.index % 2 === 0).map((w) => [{ xAxis: w.start }, { xAxis: w.end }])
        : [];

    return {
      ...theme.base,
      grid: { left: 8, right: 16, top: 36, bottom: 64 },
      legend: {
        top: 0,
        left: 4,
        icon: 'circle',
        itemWidth: 9,
        itemHeight: 9,
        itemGap: 18,
        textStyle: { color: theme.chrome.ink2, fontSize: 12 },
      },
      xAxis: {
        type: 'time',
        ...theme.axis({
          splitLine: { show: false },
          axisLabel: { color: theme.chrome.muted, fontSize: 11, hideOverlap: true, formatter: TIME_AXIS_LABELS },
        }),
      },
      yAxis: {
        type: 'value',
        name: 'Magnitude',
        nameLocation: 'middle',
        nameGap: 32,
        min: Math.floor(magRange[0] * 2) / 2,
        max: Math.ceil(magRange[1] * 2) / 2,
        ...theme.axis(),
      },
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: 0,
          filterMode: 'none',
          ...(zoom ? { startValue: zoom[0], endValue: zoom[1] } : { start: 0, end: 100 }),
        },
        {
          type: 'slider',
          xAxisIndex: 0,
          filterMode: 'none',
          height: 20,
          bottom: 10,
          ...(zoom ? { startValue: zoom[0], endValue: zoom[1] } : { start: 0, end: 100 }),
          borderColor: theme.chrome.border,
          backgroundColor: theme.chrome.page,
          fillerColor: theme.chrome.band,
          dataBackground: {
            lineStyle: { color: theme.chrome.axis, width: 1 },
            areaStyle: { color: theme.chrome.grid },
          },
          selectedDataBackground: {
            lineStyle: { color: theme.series[0], width: 1 },
            areaStyle: { color: theme.chrome.band },
          },
          handleStyle: { color: theme.chrome.surface, borderColor: theme.chrome.axis },
          moveHandleStyle: { color: theme.chrome.axis },
          textStyle: { color: theme.chrome.muted, fontSize: 10 },
          labelFormatter: (value: number) => formatDateTime(value, false).slice(0, 10),
        },
      ],
      tooltip: {
        ...(theme.base.tooltip as object),
        trigger: 'item',
        formatter: (params: any) => {
          const i = params.value[2];
          const color = catalog.kind[i] === INPUT ? theme.events.input : theme.events.test;
          const depth = catalog.depth[i];
          return [
            tooltipTitle(`M ${formatMagnitude(catalog.mag[i])} · ${catalog.id[i]}`),
            tooltipRow(color, formatDateTime(catalog.time[i]), 'UTC'),
            tooltipRow(null, formatLatLon(catalog.lat[i], catalog.lon[i]), ''),
            Number.isFinite(depth) ? tooltipRow(null, `${depth.toFixed(1)} km`, 'depth') : '',
          ].join('');
        },
      },
      series: [
        {
          type: 'scatter',
          name: 'Before start (input)',
          data: input,
          ...point(theme.events.input),
        },
        {
          type: 'scatter',
          name: 'Experiment period (test)',
          data: test,
          ...point(theme.events.test),
          markArea: bands.length ? { silent: true, itemStyle: { color: theme.chrome.band }, data: bands } : undefined,
          markLine: Number.isFinite(startMs)
            ? {
                silent: true,
                symbol: 'none',
                lineStyle: { color: theme.chrome.ink2, width: 1, type: 'solid' },
                label: {
                  formatter: 'Start',
                  position: 'insideEndTop',
                  color: theme.chrome.ink2,
                  fontSize: 11,
                },
                data: [{ xAxis: startMs }],
              }
            : undefined,
        },
      ],
    };
  }, [theme, catalog, indices, windows, startMs, zoom]);

  return <EChart option={option} height={height} ariaLabel={`Magnitude against time for ${indices.length} events`} />;
}
