'use client';

import { useMemo } from 'react';
import type { ChartOption } from '@/lib/echarts';
import EChart from './EChart';
import { useChartTheme } from './chartTheme';

export interface IntervalRow {
  label: string;
  /** Range of the test distribution (consistency) or the 95% CI (comparative). */
  lower: number | null;
  upper: number | null;
  /** Expected / median value of the test distribution (consistency tests). */
  centre: number | null;
  observed: number | null;
  /** true = not rejected / better; false = rejected / worse; null = indistinguishable. */
  passed: boolean | null;
  tooltip: string;
}

const PASS = '#1e8449';
const FAIL = '#c0392b';
const TIE = '#7f8c8d';
const CROSS = 'path://M2,0 L8,6 L14,0 L16,2 L10,8 L16,14 L14,16 L8,10 L2,16 L0,14 L6,8 L0,2 Z';

interface IntervalChartProps {
  rows: IntervalRow[];
  kind: 'consistency' | 'comparative';
  xName: string;
  ariaLabel: string;
}

/**
 * One row per model: the test distribution's range (consistency tests, as in
 * pyCSEP's consistency plots) or the information gain with its 95% interval
 * (comparative tests), with the observed value marked pass/fail.
 */
export default function IntervalChart({ rows, kind, xName, ariaLabel }: IntervalChartProps) {
  const theme = useChartTheme();
  const height = rows.length * 34 + 72;

  const option = useMemo<ChartOption>(() => {
    const { chrome } = theme;
    const values = rows
      .flatMap((r) => [r.lower, r.upper, r.observed, r.centre])
      .filter((v): v is number => v !== null && Number.isFinite(v));
    if (kind === 'comparative') values.push(0);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const pad = (max - min) * 0.06 || 1;
    const colorOf = (r: IntervalRow) => (r.passed === true ? PASS : r.passed === false ? FAIL : TIE);

    return {
      ...theme.base,
      grid: { left: 8, right: 20, top: 8, bottom: 44 },
      xAxis: {
        type: 'value',
        name: xName,
        nameLocation: 'middle',
        nameGap: 28,
        min: min - pad,
        max: max + pad,
        scale: true,
        ...theme.axis({
          axisLabel: { color: theme.chrome.muted, fontSize: 11, showMinLabel: false, showMaxLabel: false },
        }),
      },
      yAxis: {
        type: 'category',
        data: rows.map((r) => r.label),
        inverse: true,
        ...theme.axis({ axisTick: { show: false }, splitLine: { show: false }, axisLine: { show: false } }),
      },
      tooltip: {
        ...(theme.base.tooltip as object),
        trigger: 'item',
        formatter: (params: any) => rows[params.dataIndex]?.tooltip ?? '',
      },
      series: [
        {
          type: 'custom',
          name: kind === 'comparative' ? '95% interval' : 'Test distribution',
          data: rows.map((r, i) => [r.lower ?? NaN, r.upper ?? NaN, i]),
          renderItem: (params: any, api: any) => {
            const row = rows[params.dataIndex];
            if (row.lower === null || row.upper === null) return null;
            const from = api.coord([row.lower, params.dataIndex]);
            const to = api.coord([row.upper, params.dataIndex]);
            const color = kind === 'comparative' ? colorOf(row) : theme.mode === 'dark' ? '#8a9199' : '#566573';
            return {
              type: 'group',
              children: [
                {
                  type: 'line',
                  shape: { x1: from[0], y1: from[1], x2: to[0], y2: to[1] },
                  style: { stroke: color, lineWidth: 2.5, lineCap: 'round' },
                },
                {
                  type: 'line',
                  shape: { x1: from[0], y1: from[1] - 5, x2: from[0], y2: from[1] + 5 },
                  style: { stroke: color, lineWidth: 2 },
                },
                {
                  type: 'line',
                  shape: { x1: to[0], y1: to[1] - 5, x2: to[0], y2: to[1] + 5 },
                  style: { stroke: color, lineWidth: 2 },
                },
              ],
            };
          },
          z: 1,
        },
        ...(kind === 'consistency'
          ? [
              {
                type: 'scatter',
                name: 'Simulated median',
                data: rows.map((r, i) => [r.centre ?? NaN, i]),
                symbol: 'rect',
                symbolSize: 7,
                itemStyle: { color: chrome.ink2 },
                z: 2,
                tooltip: { show: false },
              },
            ]
          : []),
        {
          type: 'scatter',
          name: 'Observed',
          data: rows.map((r, i) => ({
            value: [r.observed ?? NaN, i],
            symbol: r.passed === false ? CROSS : 'circle',
            symbolSize: r.passed === false ? 13 : 11,
            itemStyle: {
              color: kind === 'comparative' && r.passed === null ? chrome.surface : colorOf(r),
              borderColor: kind === 'comparative' && r.passed === null ? TIE : chrome.surface,
              // No ring on the cross: it would eat into its thin arms.
              borderWidth: r.passed === false ? 0 : kind === 'comparative' && r.passed === null ? 2 : 1.5,
            },
          })),
          z: 3,
          markLine:
            kind === 'comparative'
              ? {
                  silent: true,
                  symbol: 'none',
                  lineStyle: { color: chrome.ink2, width: 1, type: 'solid' },
                  label: { show: false },
                  data: [{ xAxis: 0 }],
                }
              : undefined,
        },
      ],
    };
  }, [theme, rows, kind, xName]);

  return <EChart option={option} height={height} ariaLabel={ariaLabel} />;
}
