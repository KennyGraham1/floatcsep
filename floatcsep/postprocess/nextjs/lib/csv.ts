import { Children, isValidElement, type ReactNode } from 'react';

/** The plain text of rendered content, e.g. a table cell or a heading. */
export function textOf(node: ReactNode): string {
  return Children.toArray(node)
    .map((child) =>
      typeof child === 'string' || typeof child === 'number'
        ? String(child)
        : isValidElement<{ children?: ReactNode }>(child)
          ? textOf(child.props.children)
          : '',
    )
    .join('');
}

function field(value: string): string {
  return /[",\r\n]/.test(value) ? `"${value.replace(/"/g, '""')}"` : value;
}

/** Rows as CSV (RFC 4180), with a byte-order mark so spreadsheets read it as UTF-8. */
export function toCsv(header: string[], rows: string[][]): string {
  return `﻿${[header, ...rows].map((row) => row.map(field).join(',')).join('\r\n')}\r\n`;
}

/** A file name from a title: "Poisson S-test, N50L11" -> "poisson-s-test-n50l11". */
export function fileSlug(title: string): string {
  return (
    title
      .toLowerCase()
      .normalize('NFKD')
      .replace(/[^\w\s.-]/g, ' ')
      .trim()
      .replace(/[\s.]+/g, '-') || 'table'
  );
}

/** Save `text` as a file from the browser. */
export function downloadText(filename: string, text: string, type = 'text/csv;charset=utf-8'): void {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
