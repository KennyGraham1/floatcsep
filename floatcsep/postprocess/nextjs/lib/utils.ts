import { type ClassValue, clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const HTML_ESCAPES: Record<string, string> = {
  '&': '&amp;',
  '<': '&lt;',
  '>': '&gt;',
  '"': '&quot;',
  "'": '&#39;',
};

/** Escape text for HTML strings (chart and map tooltips render HTML). */
export function escapeHtml(value: unknown): string {
  return String(value ?? '').replace(/[&<>"']/g, (ch) => HTML_ESCAPES[ch]);
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

/** Min/max without spreading (spreading large arrays overflows the call stack). */
export function extent(values: ArrayLike<number>): [number, number] | null {
  let min = Infinity;
  let max = -Infinity;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (!Number.isFinite(v)) continue;
    if (v < min) min = v;
    if (v > max) max = v;
  }
  return min <= max ? [min, max] : null;
}

/** URL of a result figure served by /api/results. */
export function figureUrl(relativePath: string, download = false): string {
  const encoded = relativePath.split('/').map(encodeURIComponent).join('/');
  return `/api/results/${encoded}${download ? '?download=1' : ''}`;
}

export function doiUrl(doi: string): string {
  return /^https?:\/\//i.test(doi) ? doi : `https://doi.org/${doi.replace(/^doi:\s*/i, '')}`;
}

/**
 * Browser URL of a git remote: "git@github.com:org/repo.git" and
 * "ssh://git@host/org/repo" become "https://host/org/repo". Null if unknown.
 */
export function gitWebUrl(remote: string): string | null {
  const url = remote.trim().replace(/\.git$/, '');
  const scp = url.match(/^[\w.-]+@([^:/]+):(.+)$/);
  if (scp) return `https://${scp[1]}/${scp[2]}`;
  const ssh = url.match(/^(?:ssh|git):\/\/(?:[\w.-]+@)?([^/:]+)(?::\d+)?\/(.+)$/);
  if (ssh) return `https://${ssh[1]}/${ssh[2]}`;
  return /^https?:\/\//i.test(url) ? url : null;
}

export function zenodoUrl(id: string | number): string {
  return `https://zenodo.org/records/${id}`;
}
