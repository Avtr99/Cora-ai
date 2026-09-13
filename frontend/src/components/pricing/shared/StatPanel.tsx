import React from 'react';
import type { DeltaStat } from '@/data/pricingFactorContent';

/**
 * Companion stat to a price chart. Tinted rather than carded so it reads as a
 * panel on the same surface as the chart, not as a second card.
 */
const StatPanel: React.FC<{ stat: DeltaStat }> = ({ stat }) => (
  <div className="mt-7 rounded-lg bg-surface-base px-5 py-5 3xl:px-6 3xl:py-6 4xl:px-7 4xl:py-7">
    <p className="font-inter text-overline 3xl:text-caption 4xl:text-ui font-semibold uppercase tracking-wider text-text-muted">
      {stat.label}
    </p>
    <p className="mt-2.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
      <span className="font-inter text-lg sm:text-xl 3xl:text-2xl font-semibold tracking-tight tabular-nums text-text-primary">
        {stat.value}
      </span>
      <span className="font-inter text-body-sm 3xl:text-body text-text-secondary">{stat.unit}</span>
      <span className="font-inter text-body-sm 3xl:text-body font-semibold tabular-nums text-semantic-success-text">
        {stat.delta}
      </span>
      <span className="font-inter text-body-sm 3xl:text-body text-text-secondary">{stat.deltaLabel}</span>
    </p>
  </div>
);

export default StatPanel;
