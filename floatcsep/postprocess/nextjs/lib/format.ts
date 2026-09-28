const integer = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });

export function formatInt(value: number): string {
  return integer.format(value);
}

/** 1,284 / 12.9K / 4.2M */
export function formatCompact(value: number): string {
  return Math.abs(value) < 10_000 ? integer.format(value) : compact.format(value);
}

export function formatFixed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—';
  return value.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
}

const SUPERSCRIPT: Record<string, string> = {
  '-': '⁻',
  '0': '⁰',
  '1': '¹',
  '2': '²',
  '3': '³',
  '4': '⁴',
  '5': '⁵',
  '6': '⁶',
  '7': '⁷',
  '8': '⁸',
  '9': '⁹',
};

/** Scientific notation with a superscript exponent: 1.23 × 10⁻⁴. */
export function formatSci(value: number, digits = 3): string {
  if (!Number.isFinite(value)) return '—';
  if (value === 0) return '0';
  const exponent = Math.floor(Math.log10(Math.abs(value)));
  if (exponent >= -2 && exponent < 4) {
    return value.toLocaleString('en-US', { maximumSignificantDigits: digits });
  }
  const mantissa = value / 10 ** exponent;
  const exp = String(exponent)
    .split('')
    .map((ch) => SUPERSCRIPT[ch] ?? ch)
    .join('');
  return `${mantissa.toPrecision(digits)} × 10${exp}`;
}

/** Log-axis tick labels: 0.01, 0.1, 1, 10, 1,000 and 10⁻³ / 10⁵ beyond. */
export function formatPowerOfTen(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return '';
  const exponent = Math.round(Math.log10(value));
  if (Math.abs(value - 10 ** exponent) > 1e-9 * 10 ** exponent) return formatSci(value, 2);
  if (exponent >= -2 && exponent <= 4) return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
  const exp = String(exponent)
    .split('')
    .map((ch) => SUPERSCRIPT[ch] ?? ch)
    .join('');
  return `10${exp}`;
}

/** An expected count: 3.70, 0.0845, 27,748 */
export function formatRate(value: number): string {
  if (!Number.isFinite(value)) return '—';
  if (value === 0) return '0';
  if (Math.abs(value) >= 1000) return integer.format(value);
  if (Math.abs(value) >= 1) return value.toLocaleString('en-US', { maximumFractionDigits: 2 });
  return formatSci(value, 3);
}

export function formatMagnitude(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value) ? '—' : value.toFixed(1);
}

export function formatLatLon(lat: number, lon: number): string {
  const wrapped = ((((lon + 180) % 360) + 360) % 360) - 180;
  const ns = lat >= 0 ? 'N' : 'S';
  const ew = wrapped >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(3)}° ${ns}, ${Math.abs(wrapped).toFixed(3)}° ${ew}`;
}

export function pluralize(count: number, singular: string, plural = `${singular}s`): string {
  return `${formatInt(count)} ${count === 1 ? singular : plural}`;
}
