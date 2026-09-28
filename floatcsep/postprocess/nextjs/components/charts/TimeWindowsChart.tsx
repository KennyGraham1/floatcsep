'use client';

import { useMemo } from 'react';
import { echarts, type ChartOption } from '@/lib/echarts';
import { formatInt } from '@/lib/format';
import { formatDate, formatDuration, type TimeWindow } from '@/lib/time';
import EChart from './EChart';
import { TIME_AXIS_LABELS, tooltipRow, tooltipTitle, useChartTheme } from './chartTheme';

interface TimeWindowsChartProps {
  windows: TimeWindow[];
  /** Observed events per window (optional, shown in the tooltip). */
  counts?: number[] | null;
}

const ROW = 26;
const MAX_VISIBLE_ROWS = 14;

/** One bar per forecast time window on a UTC time axis. */
export default function TimeWindowsChart({ windows, counts }: TimeWindowsChartProps) {
  const theme = useChartTheme();
  const scroll = windows.length > MAX_VISIBLE_ROWS;
  const height = 56 + Math.min(windows.length, MAX_VISIBLE_ROWS) * ROW;

  const option = useMemo<ChartOption>(() => {
    const color = theme.series[0];
    const start = Math.min(...windows.map((w) => w.start));
    const end = Math.max(...windows.map((w) => w.end));
    return {
      ...theme.base,
      grid: { left: 8, right: scroll ? 36 : 16, top: 12, bottom: 28 },
      xAxis: {
        type: 'time',
        min: start,
        max: end,
        ...theme.axis({
          splitLine: { lineStyle: { color: theme.chrome.grid } },
          axisLabel: { color: theme.chrome.muted, fontSize: 11, hideOverlap: true, formatter: TIME_AXIS_LABELS },
        }),
      },
      yAxis: {
        type: 'category',
        inverse: true,
        data: windows.map((w) => w.label),
        ...theme.axis({ splitLine: { show: false }, axisTick: { show: false } }),
      },
      dataZoom: scroll
        ? [
            {
              type: 'slider',
              yAxisIndex: 0,
              right: 6,
              width: 14,
              startValue: 0,
              endValue: MAX_VISIBLE_ROWS - 1,
              zoomLock: true,
              showDetail: false,
              brushSelect: false,
              borderColor: 'transparent',
              backgroundColor: theme.chrome.page,
              fillerColor: theme.chrome.grid,
              handleSize: 0,
              moveHandleSize: 0,
              showDataShadow: false,
            },
            { type: 'inside', yAxisIndex: 0, zoomOnMouseWheel: false, moveOnMouseWheel: true },
          ]
        : undefined,
      tooltip: {
        ...(theme.base.tooltip as object),
        trigger: 'item',
        formatter: (params: any) => {
          const w = windows[params.dataIndex];
          const rows = [
            tooltipTitle(`${w.label} · ${formatDate(w.start)} → ${formatDate(w.end)}`),
            tooltipRow(color, formatDuration(w.end - w.start), 'duration'),
          ];
          if (counts) rows.push(tooltipRow(null, formatInt(counts[params.dataIndex] ?? 0), 'observed events'));
          return rows.join('');
        },
      },
      series: [
        {
          type: 'custom',
          name: 'Time windows',
          encode: { x: [1, 2], y: 0 },
          data: windows.map((w) => [w.index, w.start, w.end]),
          renderItem: (params: any, api: any) => {
            const y = api.value(0);
            const from = api.coord([api.value(1), y]);
            const to = api.coord([api.value(2), y]);
            const band = api.size([0, 1])[1];
            const h = Math.min(16, band * 0.62);
            const rect = echarts.graphic.clipRectByRect(
              { x: from[0], y: from[1] - h / 2, width: Math.max(3, to[0] - from[0] - 2), height: h },
              {
                x: params.coordSys.x,
                y: params.coordSys.y,
                width: params.coordSys.width,
                height: params.coordSys.height,
              },
            );
            if (!rect) return null;
            return {
              type: 'rect',
              shape: { ...rect, r: 4 },
              style: { fill: color },
              emphasis: { style: { fill: color, opacity: 0.8 } },
            };
          },
        },
      ],
    };
  }, [theme, windows, counts, scroll]);

  return (
    <EChart
      option={option}
      height={height}
      ariaLabel={`Timeline of ${windows.length} forecast time windows`}
    />
  );
}
