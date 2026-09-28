'use client';

import { useCallback, useEffect, useState } from 'react';

/**
 * State remembered in localStorage (per-viewer conveniences such as the chosen
 * basemap). Storage can be unavailable (private windows), so it is optional.
 */
export function usePersistentState<T extends string>(key: string, initial: T, allowed?: readonly T[]) {
  const [value, setValue] = useState<T>(initial);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(key) as T | null;
      if (stored !== null && (!allowed || allowed.includes(stored))) setValue(stored);
    } catch {
      // storage unavailable
    }
    // `allowed` is a constant list at every call site.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const update = useCallback(
    (next: T) => {
      setValue(next);
      try {
        window.localStorage.setItem(key, next);
      } catch {
        // storage unavailable
      }
    },
    [key],
  );

  return [value, update] as const;
}
