'use client';

import { useEffect, useMemo, useState } from 'react';
import { useThemeMode } from '@/hooks/useThemeMode';
import { CHROME, EVENT_COLORS, SERIES, type ThemeMode } from '@/lib/colors';
import { escapeHtml } from '@/lib/utils';

const FONT = '"Noto Sans Variable", system-ui, -apple-system, "Segoe UI", sans-serif';

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(query.matches);
    const onChange = () => setReduced(query.matches);
    query.addEventListener('change', onChange);
    return () => query.removeEventListener('change', onChange);
  }, []);
  return reduced;
}

export interface ChartTheme {
  mode: ThemeMode;
  chrome: (typeof CHROME)[ThemeMode];
  series: string[];
  events: { input: string; test: string };
  /** Options every chart starts from: font, recessive axes, tooltip style. */
  base: Record<string, unknown>;
  axis: (extra?: Record<string, unknown>) => Record<string, unknown>;
}

/** Colours and shared ECharts options for the current light/dark mode. */
export function useChartTheme(): ChartTheme {
  const mode = useThemeMode();
  const reducedMotion = usePrefersReducedMotion();

  return useMemo(() => {
    const chrome = CHROME[mode];
    const axis = (extra: Record<string, unknown> = {}) => ({
      axisLine: { lineStyle: { color: chrome.axis } },
      axisTick: { lineStyle: { color: chrome.axis } },
      axisLabel: { color: chrome.muted, fontSize: 11, fontFamily: FONT },
      splitLine: { lineStyle: { color: chrome.grid, width: 1, type: 'solid' } },
      nameTextStyle: { color: chrome.ink2, fontSize: 11, fontFamily: FONT },
      ...extra,
    });
    const base = {
      // Catalog times and time windows are UTC; ECharts would otherwise use local time.
      useUTC: true,
      animation: !reducedMotion,
      animationDuration: 350,
      textStyle: { fontFamily: FONT, color: chrome.ink2 },
      aria: { enabled: true },
      tooltip: {
        backgroundColor: chrome.surface,
        borderColor: chrome.border,
        borderWidth: 1,
        padding: [8, 10],
        textStyle: { color: chrome.ink, fontSize: 12, fontFamily: FONT },
        extraCssText: 'border-radius: 8px; box-shadow: 0 6px 18px rgba(0,0,0,0.14);',
      },
    };
    return {
      mode,
      chrome,
      series: SERIES[mode],
      events: EVENT_COLORS[mode],
      base,
      axis,
    };
  }, [mode, reducedMotion]);
}

/** Time-axis labels by tick level: years, months, days, then clock times. */
export const TIME_AXIS_LABELS = {
  year: '{yyyy}',
  month: '{MMM} {yyyy}',
  day: '{MMM} {d}',
  hour: '{HH}:{mm}',
  minute: '{HH}:{mm}',
  second: '{HH}:{mm}:{ss}',
  millisecond: '{HH}:{mm}:{ss}',
  none: '{yyyy}-{MM}-{dd} {HH}:{mm}',
};

/** One tooltip row: a short line key in the series colour, value first. */
export function tooltipRow(color: string | null, value: string, label: string): string {
  const key = color
    ? `<span style="display:inline-block;width:10px;height:2px;border-radius:1px;background:${color};margin-right:8px;vertical-align:middle"></span>`
    : '';
  return `<div style="display:flex;align-items:center;gap:0;line-height:1.7">${key}<b style="font-weight:600">${escapeHtml(value)}</b><span style="margin-left:6px;opacity:.72">${escapeHtml(label)}</span></div>`;
}

export function tooltipTitle(text: string): string {
  return `<div style="font-weight:600;margin-bottom:4px">${escapeHtml(text)}</div>`;
}
