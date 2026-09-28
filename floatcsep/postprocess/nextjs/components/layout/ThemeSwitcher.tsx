'use client';

import { Monitor, Moon, Sun } from 'lucide-react';
import { useTheme } from 'next-themes';
import { useEffect, useState } from 'react';
import { SegmentedControl } from '@/components/ui/SegmentedControl';

type ThemeChoice = 'light' | 'dark' | 'system';

export function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  // The stored theme is only known on the client; keep the space reserved.
  if (!mounted) return <div className="h-8 w-[104px]" aria-hidden />;

  return (
    <SegmentedControl<ThemeChoice>
      label="Colour theme"
      value={(theme as ThemeChoice) ?? 'system'}
      onChange={setTheme}
      options={[
        { value: 'light', label: <Sun />, title: 'Light theme' },
        { value: 'dark', label: <Moon />, title: 'Dark theme' },
        { value: 'system', label: <Monitor />, title: 'Match system theme' },
      ]}
    />
  );
}
