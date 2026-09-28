'use client';

import {
  Activity,
  BookOpen,
  ChartColumn,
  ExternalLink,
  LayoutDashboard,
  Map as MapIcon,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Badge } from '@/components/ui/Badge';
import { useManifest } from '@/lib/contexts/ManifestContext';
import { formatInt } from '@/lib/format';
import type { Manifest } from '@/lib/types';
import { cn } from '@/lib/utils';
import { Brand } from './Brand';
import { ThemeSwitcher } from './ThemeSwitcher';

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  count?: (manifest: Manifest) => number | null;
}

export const NAV_ITEMS: NavItem[] = [
  { href: '/experiment', label: 'Overview', icon: LayoutDashboard },
  { href: '/about', label: 'About', icon: BookOpen },
  { href: '/catalogs', label: 'Catalog', icon: Activity },
  { href: '/forecasts', label: 'Forecasts', icon: MapIcon, count: (m) => m.models.length },
  { href: '/results', label: 'Results', icon: ChartColumn },
];

const LINKS = [
  { href: 'https://floatcsep.readthedocs.io', label: 'Documentation' },
  { href: 'https://github.com/cseptesting/floatcsep', label: 'Source code' },
  { href: 'https://cseptesting.org', label: 'CSEP' },
];

export function SidebarContent({ onNavigate }: { onNavigate?: () => void }) {
  const { manifest } = useManifest();
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 shrink-0 items-center border-b px-5">
        <Link href="/experiment" onClick={onNavigate} aria-label="floatCSEP overview" className="rounded-md">
          <Brand />
        </Link>
      </div>

      {manifest && (
        <div className="border-b px-5 py-4">
          <p className="text-2xs font-semibold uppercase tracking-[0.08em] text-ink-3">Experiment</p>
          <p className="mt-1.5 line-clamp-2 text-[0.84rem] font-semibold leading-5 text-ink" title={manifest.name}>
            {manifest.name}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {manifest.exp_class && <Badge tone="accent">{manifest.exp_class}</Badge>}
            <Badge>
              {manifest.time_windows.length === 1 ? '1 window' : `${formatInt(manifest.time_windows.length)} windows`}
            </Badge>
          </div>
          <p className="mt-2 text-xs tabular text-ink-3">
            {manifest.start_date} → {manifest.end_date}
          </p>
        </div>
      )}

      <nav aria-label="Main" className="flex-1 overflow-y-auto px-3 py-3">
        <ul className="space-y-0.5">
          {NAV_ITEMS.map((item) => {
            const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
            const count = manifest && item.count ? item.count(manifest) : null;
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={active ? 'page' : undefined}
                  className={cn(
                    'group relative flex h-9 items-center gap-2.5 rounded-md px-2.5 text-[0.8rem] font-medium transition-colors',
                    active ? 'bg-surface-2 text-ink' : 'text-ink-2 hover:bg-surface-2/70 hover:text-ink',
                  )}
                >
                  {active && <span className="absolute inset-y-2 left-0 w-[3px] rounded-r bg-accent" aria-hidden />}
                  <Icon
                    className={cn('size-4', active ? 'text-accent' : 'text-ink-3 group-hover:text-ink-2')}
                    aria-hidden
                  />
                  {item.label}
                  {count !== null && count !== undefined && (
                    <span className="ml-auto text-2xs tabular text-ink-3">{formatInt(count)}</span>
                  )}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <div className="space-y-4 border-t px-5 py-4">
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-ink-3">Theme</span>
          <ThemeSwitcher />
        </div>
        <ul className="space-y-1.5 text-xs">
          {LINKS.map((link) => (
            <li key={link.href}>
              <a
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-ink-2 hover:text-ink"
              >
                {link.label}
                <ExternalLink className="size-3 text-ink-3" aria-hidden />
              </a>
            </li>
          ))}
        </ul>
        {manifest && (manifest.floatcsep_version || manifest.pycsep_version) && (
          <p className="text-2xs tabular text-ink-3">
            {manifest.floatcsep_version && `floatCSEP ${manifest.floatcsep_version}`}
            {manifest.floatcsep_version && manifest.pycsep_version && ' · '}
            {manifest.pycsep_version && `pyCSEP ${manifest.pycsep_version}`}
          </p>
        )}
      </div>
    </div>
  );
}
