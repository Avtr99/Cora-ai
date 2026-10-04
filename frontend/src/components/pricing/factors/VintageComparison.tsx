import React from 'react';
import {
  MARKET_SOURCES,
  VINTAGE_INSIGHTS,
  VINTAGE_PRICE_ARIA_LABEL,
  VINTAGE_PRICE_COMPARISON,
  VINTAGE_PRICE_LEGEND,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import Band from '@/components/pricing/shared/Band';
import BarComparison from '@/components/pricing/shared/BarComparison';
import { toBarItems } from '@/components/pricing/shared/barItems';
import DataCard from '@/components/pricing/shared/DataCard';
import PanelFooter from '@/components/pricing/shared/PanelFooter';
import VintageStrip from '@/components/pricing/shared/VintageStrip';

const VintageComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => {
  const [reporting, methodology, quality] = VINTAGE_INSIGHTS;

  return (
  <>
    <DataCard activeForce="vintage">
      <Band first label="2024 average transaction price">
        <BarComparison
          items={toBarItems(VINTAGE_PRICE_COMPARISON)}
          label={VINTAGE_PRICE_ARIA_LABEL}
          legend={
            <>
              <b className="font-semibold text-text-primary tabular-nums">{VINTAGE_PRICE_LEGEND.value}</b>{' '}
              {VINTAGE_PRICE_LEGEND.text}
            </>
          }
        />
      </Band>
      <Band label="Why buyers prefer recent vintages">
        <VintageStrip />
        <ul className="mt-6 grid gap-x-8 gap-y-3 border-t border-border-ui pt-5 md:grid-cols-2">
          {[reporting, methodology].map((insight) => (
            <li key={insight.id} className="text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
              <b className="font-semibold text-text-primary">{insight.title}.</b> {insight.body}
            </li>
          ))}
        </ul>
        <p className="mt-4 rounded-lg bg-surface-base px-3.5 py-3 text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
          <b className="font-semibold text-text-primary">{quality.title}.</b> {quality.body}
        </p>
      </Band>
    </DataCard>
    <PanelFooter activeForce="vintage" onSelect={onForceChange} sources={MARKET_SOURCES} />
  </>
  );
};

export default VintageComparison;
