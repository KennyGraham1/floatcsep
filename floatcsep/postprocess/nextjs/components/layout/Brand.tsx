import Image from 'next/image';
import { cn } from '@/lib/utils';

export const FLOATCSEP_URL = 'https://github.com/cseptesting/floatcsep';

/** The floatCSEP logo, linking to the project's home page, as in the Panel dashboard. */
export function Brand({ className }: { className?: string }) {
  return (
    <a
      href={FLOATCSEP_URL}
      target="_blank"
      rel="noopener noreferrer"
      aria-label="floatCSEP on GitHub (opens in a new tab)"
      title="floatCSEP on GitHub"
      className={cn('inline-flex shrink-0 rounded-md', className)}
    >
      <Image
        src="/logos/floatcsep.png"
        alt="floatCSEP"
        width={333}
        height={160}
        priority
        className="h-11 w-auto dark:brightness-125"
      />
    </a>
  );
}
