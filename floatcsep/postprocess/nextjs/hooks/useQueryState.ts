'use client';

import { usePathname, useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

/**
 * Page selections (model, time window, test...) live in the URL, so a view can be
 * bookmarked, shared and survives a reload. Pages using this must be wrapped in
 * <Suspense> (Next.js requirement for useSearchParams).
 */
export function useQueryState() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();

  const set = useCallback(
    (updates: Record<string, string | number | null>) => {
      const next = new URLSearchParams(params.toString());
      for (const [key, value] of Object.entries(updates)) {
        if (value === null || value === '') next.delete(key);
        else next.set(key, String(value));
      }
      const query = next.toString();
      router.replace(query ? `${pathname}?${query}` : pathname, { scroll: false });
    },
    [params, pathname, router],
  );

  return { params, set };
}

/** Index of `name` in `items` (by name), or `fallback`. */
export function indexByName<T extends { name: string }>(items: T[], name: string | null, fallback = 0): number {
  if (name === null) return fallback;
  const i = items.findIndex((item) => item.name === name);
  return i >= 0 ? i : fallback;
}

/** A 1-based window number from the URL as a 0-based index within [0, count). */
export function windowIndexFromParam(value: string | null, count: number, fallback: number): number {
  const n = value === null ? NaN : Number(value);
  return Number.isInteger(n) && n >= 1 && n <= count ? n - 1 : fallback;
}
