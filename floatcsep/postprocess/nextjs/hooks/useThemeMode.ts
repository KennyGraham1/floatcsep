'use client';

import { useTheme } from 'next-themes';
import type { ThemeMode } from '@/lib/colors';

/** The resolved light/dark mode, for colours of canvas-based charts and maps. */
export function useThemeMode(): ThemeMode {
  const { resolvedTheme } = useTheme();
  return resolvedTheme === 'dark' ? 'dark' : 'light';
}
