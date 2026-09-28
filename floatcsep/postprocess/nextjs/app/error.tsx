'use client';

import { useEffect } from 'react';
import { ErrorState } from '@/components/ui/States';

export default function PageError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="rounded-xl border bg-surface shadow-card">
      <ErrorState
        title="This page could not be displayed"
        message={error.message}
        details={error.stack}
        onRetry={reset}
      />
    </div>
  );
}
