'use client';

import { useMemo } from 'react';
import { useCatalog } from '@/lib/api';
import { toCatalog } from '@/lib/catalog';
import { parseUtc } from '@/lib/time';
import type { Manifest } from '@/lib/types';

/** The experiment's catalog as typed arrays, with events classed input/test. */
export function useObservedCatalog(manifest: Manifest) {
  const { data, error, isLoading, mutate } = useCatalog(manifest.catalog.available);
  const startMs = parseUtc(manifest.start_date);
  const catalog = useMemo(() => (data ? toCatalog(data, startMs) : null), [data, startMs]);
  return { catalog, error, isLoading, reload: mutate, startMs };
}
