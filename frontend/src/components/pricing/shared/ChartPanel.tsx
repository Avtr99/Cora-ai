import React from 'react';
import type { ForceId } from '@/data/pricingData';
import BandLabel from '@/components/pricing/shared/BandLabel';
import FactorHeader from '@/components/pricing/shared/FactorHeader';

/**
 * Chart panel for the chart-plus-card factors (type, integrity, vintage).
 * Two columns starting on the same horizontal line: the section title on the
 * card heading on the right. The card box follows its heading directly, so
 * the right column reads as one unit with no gap. On mobile everything
 * stacks in reading order: title, chart, card heading, card box.
 */
const ChartPanel: React.FC<{
  activeForce: ForceId;
  chart: React.ReactNode;
  asideLabel: string;
  aside: React.ReactNode;
}> = ({ activeForce, chart, asideLabel, aside }) => (
  <article>
    <div className="grid items-start gap-8 lg:grid-cols-[minmax(0,1.35fr)_minmax(0,0.85fr)] lg:gap-8 xl:gap-12">
      <div className="min-w-0">
        <FactorHeader activeForce={activeForce} />
        <div className="mt-6 3xl:mt-8 4xl:mt-10">{chart}</div>
      </div>
      <div className="min-w-0">
        <BandLabel>{asideLabel}</BandLabel>
        <aside className="mt-4 min-w-0 rounded-xl border border-border-ui bg-surface-card p-5 3xl:p-7 4xl:p-8 shadow-xs sm:p-6">
          {aside}
        </aside>
      </div>
    </div>
  </article>
);

export default ChartPanel;
