import React from 'react';
import BandLabel from '@/components/pricing/shared/BandLabel';

/**
 * One labelled evidence band: a section heading, an optional sub-line, then a
 * single bordered card holding the visual. Bands are separated by spacing
 * alone, so a page reads as one surface with distinct groups.
 */
const Band: React.FC<{
  label: string;
  sub?: string;
  /** Tighter top margin for the band directly under the factor heading. */
  first?: boolean;
  /** Card carries no padding; its children lay out their own cells. */
  bare?: boolean;
  className?: string;
  children: React.ReactNode;
}> = ({ label, sub, first = false, bare = false, className = '', children }) => (
  <section className={`${first ? '' : 'mt-10 3xl:mt-14 4xl:mt-16'} ${className}`}>
    <BandLabel>{label}</BandLabel>
    {sub ? (
      <p className="mt-2 max-w-[70ch] text-pretty font-inter text-ui 3xl:text-sm 4xl:text-base leading-relaxed text-text-muted">
        {sub}
      </p>
    ) : null}
    <div
      className={`mt-4 rounded-xl border border-border-ui bg-surface-card shadow-xs ${
        bare ? '' : 'p-5 3xl:p-7 4xl:p-8 sm:p-6'
      }`}
    >
      {children}
    </div>
  </section>
);

export default Band;
