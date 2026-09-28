import { cva, type VariantProps } from 'class-variance-authority';
import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

const badgeStyles = cva(
  'inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-px text-2xs font-medium',
  {
    variants: {
      tone: {
        neutral: 'border-line bg-surface-2 text-ink-2',
        accent: 'border-accent/25 bg-accent/10 text-accent',
        info: 'border-focus/25 bg-focus/10 text-link',
        good: 'border-good/25 bg-good/10 text-good',
        warning: 'border-warning/30 bg-warning/10 text-warning',
      },
    },
    defaultVariants: { tone: 'neutral' },
  },
);

type BadgeProps = HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeStyles>;

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeStyles({ tone }), className)} {...props} />;
}
