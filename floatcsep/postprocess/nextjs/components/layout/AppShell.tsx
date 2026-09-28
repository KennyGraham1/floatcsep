'use client';

import { Menu, X } from 'lucide-react';
import { usePathname } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';
import { Button } from '@/components/ui/Button';
import { ErrorState, Skeleton } from '@/components/ui/States';
import { CATALOG_URL, prefetch } from '@/lib/api';
import { useManifest } from '@/lib/contexts/ManifestContext';
import { Brand } from './Brand';
import { NAV_ITEMS, SidebarContent } from './Sidebar';

function PageSkeleton() {
  return (
    <div aria-busy="true" aria-label="Loading the experiment">
      <Skeleton className="h-7 w-72" />
      <Skeleton className="mt-3 h-4 w-96 max-w-full" />
      <div className="mt-8 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }, (_, i) => (
          <Skeleton key={i} className="h-[92px] rounded-xl" />
        ))}
      </div>
      <div className="mt-5 grid gap-5 xl:grid-cols-2">
        <Skeleton className="h-80 rounded-xl" />
        <Skeleton className="h-80 rounded-xl" />
      </div>
    </div>
  );
}

export default function AppShell({ children }: { children: ReactNode }) {
  const { manifest, isLoading, error, reload } = useManifest();
  const pathname = usePathname();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // Parse the catalog in the background: the Catalog and Forecasts pages use it.
  useEffect(() => {
    if (!manifest?.catalog.available) return;
    const timer = window.setTimeout(() => prefetch(CATALOG_URL), 400);
    return () => window.clearTimeout(timer);
  }, [manifest]);

  useEffect(() => {
    const page = NAV_ITEMS.find((item) => pathname.startsWith(item.href))?.label;
    document.title = [page, manifest?.name, 'floatCSEP'].filter(Boolean).join(' · ');
  }, [pathname, manifest?.name]);

  useEffect(() => setDrawerOpen(false), [pathname]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && setDrawerOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [drawerOpen]);

  let content: ReactNode;
  if (error) {
    content = (
      <div className="rounded-xl border bg-surface shadow-card">
        <ErrorState
          title="The experiment could not be loaded"
          message={error.message}
          details={error.details}
          onRetry={() => reload()}
        />
      </div>
    );
  } else if (isLoading || !manifest) {
    content = <PageSkeleton />;
  } else {
    content = children;
  }

  return (
    <div className="flex min-h-screen">
      <a
        href="#main-content"
        className="sr-only z-50 rounded-md bg-ink px-3 py-2 text-sm text-surface focus:not-sr-only focus:fixed focus:left-4 focus:top-4"
      >
        Skip to main content
      </a>

      <aside className="sticky top-0 hidden h-screen w-[248px] shrink-0 border-r bg-surface lg:block">
        <SidebarContent />
      </aside>

      {drawerOpen && (
        <div className="fixed inset-0 z-[1100] lg:hidden" role="dialog" aria-modal="true" aria-label="Navigation">
          <div className="absolute inset-0 animate-fade-in bg-black/40" onClick={() => setDrawerOpen(false)} />
          <div className="absolute inset-y-0 left-0 w-[280px] max-w-[85vw] border-r bg-surface shadow-overlay">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Close navigation"
              onClick={() => setDrawerOpen(false)}
              className="absolute right-3 top-3"
            >
              <X />
            </Button>
            <SidebarContent onNavigate={() => setDrawerOpen(false)} />
          </div>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-[1050] flex h-14 items-center gap-3 border-b bg-surface/90 px-4 backdrop-blur lg:hidden">
          <Button variant="ghost" size="icon" aria-label="Open navigation" onClick={() => setDrawerOpen(true)}>
            <Menu />
          </Button>
          <Brand />
          {manifest && <span className="ml-1 min-w-0 truncate text-xs text-ink-3">{manifest.name}</span>}
        </header>

        <main id="main-content" tabIndex={-1} className="flex-1 px-4 py-6 outline-none sm:px-6 lg:px-8 lg:py-8">
          <div className="mx-auto w-full max-w-[1440px]">{content}</div>
        </main>
      </div>
    </div>
  );
}
