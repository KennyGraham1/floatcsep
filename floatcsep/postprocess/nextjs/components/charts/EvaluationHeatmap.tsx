'use client';

import { useMemo } from 'react';
import { useThemeMode } from '@/hooks/useThemeMode';
import { rampColor } from '@/lib/colors';
import type { ChartOption } from '@/lib/echarts';
import EChart from './EChart';
import { useChartTheme } from './chartTheme';

export interface HeatCell {
  row: number;
  col: number;
  value: number | null;
  /** false = rejected (score) or significantly worse (information gain). */
  passed: boolean | null;
  label: string;
  /** Tooltip HTML (already escaped). */
  tooltip: string;
}

export type HeatScale = { kind: 'score'; threshold: number } | { kind: 'diverging'; limit: number };

// Test scores, as in the global experiment's heatmaps: reds below the
// significance threshold, greens above it.
const SCORE_STOPS = ['#7b241c', '#c0392b', '#f1948a', '#fdebd0', '#abebc6', '#52be80', '#1e8449'];
const DIVERGING = {
  light: ['#e34948', '#f0efec', '#2a78d6'],
  dark: ['#e66767', '#383835', '#3987e5'],
};

/** Narrowest column, in pixels, that still fits a two-decimal label. */
const MIN_COLUMN = 46;

function fillFor(value: number, scale: HeatScale, mode: 'light' | 'dark'): string {
  if (scale.kind === 'score') {
    const { threshold } = scale;
    const t = value < threshold ? (value / threshold) * 0.5 : 0.5 + ((value - threshold) / (1 - threshold)) * 0.5;
    return rampColor(SCORE_STOPS, t);
  }
  const t = 0.5 + 0.5 * Math.max(-1, Math.min(1, value / (scale.limit || 1)));
  return rampColor(DIVERGING[mode], t);
}

function isDark(color: string): boolean {
  const [r, g, b] = (color.match(/\d+/g) ?? ['255', '255', '255']).map(Number);
  return 0.299 * r + 0.587 * g + 0.114 * b < 128;
}

interface EvaluationHeatmapProps {
  rows: string[];
  columns: string[];
  cells: HeatCell[];
  scale: HeatScale;
  xName?: string;
  ariaLabel: string;
  selected?: { row: number; col: number } | null;
  onSelect?: (row: number, col: number) => void;
}

export default function EvaluationHeatmap({
  rows,
  columns,
  cells,
  scale,
  xName,
  ariaLabel,
  selected,
  onSelect,
}: EvaluationHeatmapProps) {
  const theme = useChartTheme();
  const rowHeight = 34;
  const height = rows.length * rowHeight + (xName ? 64 : 44);
  // Narrow screens scroll the heatmap sideways instead of squeezing the cells
  // below the width of their labels.
  const minWidth = Math.round(Math.max(0, ...rows.map((r) => r.length)) * 6.5 + 16 + columns.length * MIN_COLUMN);

  const option = useMemo<ChartOption>(() => {
    const { chrome } = theme;
    return {
      ...theme.base,
      grid: { left: 8, right: 8, top: 8, bottom: xName ? 44 : 24 },
      xAxis: {
        type: 'category',
        data: columns,
        name: xName,
        nameLocation: 'middle',
        nameGap: 30,
        ...theme.axis({
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: {
            color: chrome.ink2,
            fontSize: 11,
            interval: 0,
            hideOverlap: true,
            formatter: (value: string, index: number) =>
              selected && selected.col === index ? `{selected|${value}}` : value,
            rich: { selected: { color: chrome.ink, fontWeight: 700, fontSize: 11.5 } },
          },
        }),
      },
      yAxis: {
        type: 'category',
        data: rows,
        inverse: true,
        ...theme.axis({
          axisLine: { show: false },
          axisTick: { show: false },
          splitLine: { show: false },
          axisLabel: { color: chrome.ink2, fontSize: 11 },
        }),
      },
      tooltip: {
        ...(theme.base.tooltip as object),
        trigger: 'item',
        // Inside the chart: the scroll container below would clip it otherwise.
        confine: true,
        formatter: (params: any) => cells[params.dataIndex]?.tooltip ?? '',
      },
      series: [
        {
          type: 'custom',
          cursor: onSelect ? 'pointer' : 'default',
          data: cells.map((c) => [c.col, c.row]),
          renderItem: (params: any, api: any) => {
            const cell = cells[params.dataIndex];
            const [cx, cy] = api.coord([api.value(0), api.value(1)]);
            const [w, h] = api.size([1, 1]);
            const gap = 2;
            const x = cx - w / 2 + gap / 2;
            const y = cy - h / 2 + gap / 2;
            const width = w - gap;
            const heightCell = h - gap;
            const fill = cell.value === null ? chrome.grid : fillFor(cell.value, scale, theme.mode);
            const rejected = cell.passed === false;
            const isSelected = selected && selected.row === cell.row && selected.col === cell.col;
            const children: any[] = [
              {
                type: 'rect',
                shape: { x, y, width, height: heightCell, r: 4 },
                style: {
                  fill,
                  stroke: isSelected ? chrome.ink : rejected ? chrome.ink : 'transparent',
                  lineWidth: isSelected ? 2.5 : rejected ? 1.6 : 0,
                },
              },
            ];
            if (rejected && scale.kind === 'score') {
              // Hatching: the verdict does not rely on colour alone.
              const lines = [];
              for (let d = -heightCell; d < width; d += 7) {
                lines.push({
                  type: 'line',
                  shape: { x1: x + d, y1: y + heightCell, x2: x + d + heightCell, y2: y },
                  style: { stroke: 'rgba(255,255,255,0.45)', lineWidth: 1 },
                  silent: true,
                });
              }
              children.push({
                type: 'group',
                clipPath: { type: 'rect', shape: { x, y, width, height: heightCell, r: 4 } },
                children: lines,
                silent: true,
              });
            }
            children.push({
              type: 'text',
              silent: true,
              style: {
                text: cell.label,
                x: cx,
                y: cy,
                align: 'center',
                verticalAlign: 'middle',
                fill: cell.value === null ? chrome.muted : isDark(fill) ? '#ffffff' : '#121211',
                fontSize: 11.5,
                fontWeight: cell.passed === true && scale.kind === 'diverging' ? 700 : 500,
                fontFamily: (theme.base.textStyle as { fontFamily: string }).fontFamily,
              },
            });
            return { type: 'group', children };
          },
        },
      ],
    };
  }, [theme, rows, columns, cells, scale, xName, selected, onSelect]);

  const events = useMemo(
    () =>
      onSelect
        ? {
            click: (params: any) => {
              const cell = cells[params.dataIndex];
              if (cell) onSelect(cell.row, cell.col);
            },
          }
        : undefined,
    [onSelect, cells],
  );

  return (
    <div className="overflow-x-auto">
      <div style={{ minWidth }}>
        <EChart option={option} height={height} ariaLabel={ariaLabel} onEvents={events} />
      </div>
    </div>
  );
}

/** Legend for the score scale: the ramp with the threshold marked. */
export function ScoreLegend({ threshold, label }: { threshold: number; label: string }) {
  const position = 50;
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-2">
      <div className="flex items-center gap-2">
        <span>{label}</span>
        <span
          className="relative inline-block h-2.5 w-40 rounded-sm ring-1 ring-line"
          style={{ background: `linear-gradient(to right, ${SCORE_STOPS.join(', ')})` }}
        >
          <span className="absolute inset-y-[-3px] w-0.5 bg-ink" style={{ left: `${position}%` }} aria-hidden />
        </span>
        <span className="tabular text-ink-3">0 · {threshold} · 1</span>
      </div>
      <span className="inline-flex items-center gap-1.5">
        <span
          className="inline-block size-3 rounded-[3px] ring-[1.5px] ring-ink"
          style={{ background: 'repeating-linear-gradient(135deg, #c0392b 0 3px, #f1948a 3px 5px)' }}
          aria-hidden
        />
        Rejected (outlined, hatched)
      </span>
    </div>
  );
}

/** Legend for information gain: red worse, blue better than the reference. */
export function DivergingLegend({ limit, label }: { limit: number; label: string }) {
  const mode = useThemeMode();
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-ink-2">
      <div className="flex items-center gap-2">
        <span>{label}</span>
        <span
          className="inline-block h-2.5 w-40 rounded-sm ring-1 ring-line"
          style={{ background: `linear-gradient(to right, ${DIVERGING[mode].join(', ')})` }}
        />
        <span className="tabular text-ink-3">
          −{limit.toFixed(1)} · 0 · +{limit.toFixed(1)}
        </span>
      </div>
      <span>Bold: significantly better · outlined: significantly worse (95% interval excludes zero)</span>
    </div>
  );
}
