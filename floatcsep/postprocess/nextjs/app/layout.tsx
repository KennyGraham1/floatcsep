import type { Metadata, Viewport } from 'next';
import '@fontsource-variable/noto-sans';
import 'leaflet/dist/leaflet.css';
import './globals.css';
import AppShell from '@/components/layout/AppShell';
import { ThemeProvider } from '@/components/ThemeProvider';
import { ManifestProvider } from '@/lib/contexts/ManifestContext';

export const metadata: Metadata = {
  title: 'floatCSEP',
  description: 'Interactive dashboard for floatCSEP earthquake forecasting experiments',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#f9f9f7' },
    { media: '(prefers-color-scheme: dark)', color: '#0d0d0d' },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // next-themes sets the theme class on <html> before hydration.
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <ManifestProvider>
            <AppShell>{children}</AppShell>
          </ManifestProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
