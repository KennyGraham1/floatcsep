import { Compass } from 'lucide-react';
import Link from 'next/link';
import { EmptyState } from '@/components/ui/States';
import { buttonStyles } from '@/components/ui/Button';

export default function NotFound() {
  return (
    <div className="rounded-xl border bg-surface shadow-card">
      <EmptyState
        icon={Compass}
        title="Page not found"
        description="This page does not exist in the dashboard."
        action={
          <Link href="/experiment" className={buttonStyles({ size: 'sm' })}>
            Go to the overview
          </Link>
        }
      />
    </div>
  );
}
