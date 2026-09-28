/**
 * Dates in floatCSEP are UTC. JavaScript parses "YYYY-MM-DDTHH:MM" without an
 * offset as *local* time, so everything here goes through explicit UTC parsing.
 */

const DAY = 86_400_000;

export interface TimeWindow {
  index: number;
  label: string;
  start: number;
  end: number;
  text: string;
}

/** Parse "YYYY-MM-DD" or "YYYY-MM-DDTHH:MM[:SS]" as UTC epoch milliseconds. */
export function parseUtc(value: string | null | undefined): number {
  if (!value) return NaN;
  const trimmed = value.trim().replace(' ', 'T');
  const hasZone = /(Z|[+-]\d{2}:?\d{2})$/.test(trimmed);
  return Date.parse(hasZone ? trimmed : trimmed.length <= 10 ? `${trimmed}T00:00:00Z` : `${trimmed}Z`);
}

/** Parse a floatCSEP time window string such as "2016-08-25 to 2016-08-26". */
export function parseTimeWindow(text: string, index: number): TimeWindow {
  const [a, b] = text.split(/\s+to\s+|_/);
  const start = parseUtc(a);
  const end = parseUtc(b ?? a);
  return { index, label: `T${index + 1}`, start, end, text };
}

export function parseTimeWindows(windows: string[]): TimeWindow[] {
  return windows.map(parseTimeWindow);
}

/** True when each window starts at or after the previous one ends (incremental). */
export function windowsAreDisjoint(windows: TimeWindow[]): boolean {
  return windows.every((w, i) => i === 0 || w.start >= windows[i - 1].end - 1000);
}

const pad = (n: number) => String(n).padStart(2, '0');

export function formatDate(ms: number): string {
  if (!Number.isFinite(ms)) return '—';
  const d = new Date(ms);
  return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`;
}

export function formatDateTime(ms: number, seconds = true): string {
  if (!Number.isFinite(ms)) return '—';
  const d = new Date(ms);
  const time = `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}${seconds ? `:${pad(d.getUTCSeconds())}` : ''}`;
  return `${formatDate(ms)} ${time}`;
}

/** Human duration: "6 hours", "7 days", "5 months", "1 year", "16.2 years". */
export function formatDuration(ms: number): string {
  if (!Number.isFinite(ms) || ms < 0) return '—';
  const days = ms / DAY;
  if (days < 1) {
    const hours = Math.round(ms / 3_600_000);
    return `${hours} hour${hours === 1 ? '' : 's'}`;
  }
  const years = days / 365.25;
  const wholeYears = Math.round(years);
  // 365 days is 0.9993 of a mean year; calendar years count as whole years.
  if (wholeYears >= 1 && Math.abs(years - wholeYears) < 0.01) {
    return `${wholeYears} year${wholeYears === 1 ? '' : 's'}`;
  }
  if (years >= 2) return `${years.toFixed(1)} years`;
  if (days >= 90) {
    const months = Math.round(days / 30.44);
    return `${months} months`;
  }
  const d = Math.round(days);
  return `${d.toLocaleString('en-US')} day${d === 1 ? '' : 's'}`;
}
