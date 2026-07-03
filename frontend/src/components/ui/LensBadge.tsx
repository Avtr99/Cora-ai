import React from 'react';
import { cn } from '@/lib/utils';
import { CASE_STUDY } from '@/lib/colors';

interface LensBadgeProps {
  label: string;
  className?: string;
}

/**
 * LensBadge displays a case-study lens label (e.g., "Understanding high quality credits")
 * with the canonical case-study chip styling. Used wherever a lens tag appears so the
 * same component and color properties are shared across the recommendation cards and the
 * case-study pages.
 */
export const LensBadge: React.FC<LensBadgeProps> = ({ label, className }) => {
  return (
    <span
      className={cn(
        'inline-flex items-center justify-center rounded-full',
        'px-3 py-1 font-inter text-xs font-medium whitespace-nowrap w-fit',
        className
      )}
      style={{
        backgroundColor: CASE_STUDY.lens.bg,
        color: CASE_STUDY.lens.text,
      }}
    >
      {label}
    </span>
  );
};

export default LensBadge;
