/**
 * Colours for charts and maps (canvas and ECharts cannot read CSS variables).
 * Keep the chrome values in sync with the tokens in app/globals.css.
 *
 * - Categorical slots are a validated colour-blind-safe order; assign them in
 *   order and never by rank. Scatter/map forms use at most the first three.
 * - Forecast rates use a "semantic heat" sequential ramp (lightness monotonic):
 *   yellow→dark red on light, purple→bright yellow (inferno-like) on dark. The
 *   ends nearest the surface are trimmed so low rates remain visible.
 */

export type ThemeMode = 'light' | 'dark';

export const SERIES: Record<ThemeMode, string[]> = {
  light: ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'],
  dark: ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#008300', '#9085e9', '#e66767'],
};

/** Catalog event classes: slot 1 (input/before start) and slot 2 (test period). */
export const EVENT_COLORS: Record<ThemeMode, { input: string; test: string }> = {
  light: { input: SERIES.light[0], test: SERIES.light[1] },
  dark: { input: SERIES.dark[0], test: SERIES.dark[1] },
};

export interface Chrome {
  surface: string;
  page: string;
  ink: string;
  ink2: string;
  muted: string;
  grid: string;
  axis: string;
  border: string;
  band: string;
  accent: string;
}

export const CHROME: Record<ThemeMode, Chrome> = {
  light: {
    surface: '#ffffff',
    page: '#f9f9f7',
    ink: '#121211',
    ink2: '#52514e',
    muted: '#898781',
    grid: '#e1e0d9',
    axis: '#c3c2b7',
    border: '#e4e3dd',
    band: 'rgba(42, 120, 214, 0.07)',
    accent: '#b3141f',
  },
  dark: {
    surface: '#1a1a19',
    page: '#0d0d0d',
    ink: '#f4f4f2',
    ink2: '#c3c2b7',
    muted: '#898781',
    grid: '#2c2c2a',
    axis: '#383835',
    border: '#2e2e2b',
    band: 'rgba(57, 135, 229, 0.10)',
    accent: '#f0616d',
  },
};

/** Sequential ramps for forecast rates, low → high. */
export const HEAT: Record<ThemeMode, string[]> = {
  light: ['#fed976', '#feb24c', '#fd8d3c', '#fc4e2a', '#e31a1c', '#bd0026', '#800026'],
  dark: ['#4a0c6b', '#781c6d', '#a52c60', '#cf4446', '#ed6925', '#fb9b06', '#f7d13d', '#fcffa4'],
};

/** Region cells on the overview map. */
export const REGION_FILL: Record<ThemeMode, string> = {
  light: '#2a78d6',
  dark: '#3987e5',
};

function hexToRgb(hex: string): [number, number, number] {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/** A 256-entry RGB lookup table interpolated along a ramp. */
export function rampTable(stops: string[], size = 256): Uint8ClampedArray {
  const rgb = stops.map(hexToRgb);
  const table = new Uint8ClampedArray(size * 3);
  for (let i = 0; i < size; i++) {
    const t = (i / (size - 1)) * (rgb.length - 1);
    const k = Math.min(rgb.length - 2, Math.floor(t));
    const f = t - k;
    for (let c = 0; c < 3; c++) {
      table[i * 3 + c] = rgb[k][c] + (rgb[k + 1][c] - rgb[k][c]) * f;
    }
  }
  return table;
}

/** CSS colour at position t ∈ [0, 1] of a ramp. */
export function rampColor(stops: string[], t: number): string {
  const rgb = stops.map(hexToRgb);
  const x = Math.min(1, Math.max(0, Number.isFinite(t) ? t : 0)) * (rgb.length - 1);
  const k = Math.min(rgb.length - 2, Math.floor(x));
  const f = x - k;
  const mix = (c: number) => Math.round(rgb[k][c] + (rgb[k + 1][c] - rgb[k][c]) * f);
  return `rgb(${mix(0)}, ${mix(1)}, ${mix(2)})`;
}

export function rampGradient(stops: string[], direction = 'to right'): string {
  return `linear-gradient(${direction}, ${stops.join(', ')})`;
}

export function withAlpha(hex: string, alpha: number): string {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
