import React from 'react';
import { TrendingDown, TrendingUp } from 'lucide-react';
import type { PriceOutlook } from '@/data/pricingFactorContent';
import ContextSection from '@/components/pricing/shared/ContextSection';

/** Badge text and icon colors per trend, backed by --color-trend-* theme tokens. */
const TREND_TEXT_CLASSES = {
  rising: 'text-trend-rising',
  declining: 'text-trend-declining',
} as const;

const TREND_ICON_CLASSES = {
  rising: 'text-trend-rising-icon',
  declining: 'text-trend-declining-icon',
} as const;

const OutlookCards: React.FC<{ outlooks: PriceOutlook[] }> = ({ outlooks }) => (
  <ContextSection label="What it means for prices">
    <div className="grid gap-5 md:grid-cols-2">
      {outlooks.map((outlook) => {
        const TrendIcon = outlook.trend === 'rising' ? TrendingUp : TrendingDown;
        return (
          <section
            key={outlook.badge}
            className="flex h-full flex-col rounded-xl border border-border-ui bg-surface-card p-5 3xl:p-7 4xl:p-8 shadow-xs sm:p-6"
          >
            <div className="flex items-start justify-between gap-3">
              <span
                className={`font-inter text-caption 3xl:text-xs 4xl:text-sm font-semibold ${TREND_TEXT_CLASSES[outlook.trend]}`}
              >
                {outlook.badge}
              </span>
              <span className={TREND_ICON_CLASSES[outlook.trend]}>
                <TrendIcon strokeWidth={2} aria-hidden={true} className="h-[18px] w-[18px] 3xl:h-5 3xl:w-5 4xl:h-6 4xl:w-6" />
              </span>
            </div>
            <h4 className="mt-5 font-poppins text-base sm:text-lg 3xl:text-xl font-semibold leading-tight text-text-primary">{outlook.title}</h4>
            <p className="mt-2 max-w-[62ch] font-inter text-body-sm 3xl:text-body 4xl:text-lg leading-relaxed text-text-secondary">{outlook.body}</p>
          </section>
        );
      })}
    </div>
  </ContextSection>
);

export default OutlookCards;
