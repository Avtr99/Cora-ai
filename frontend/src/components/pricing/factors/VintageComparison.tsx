import React from 'react';
import BookIcon from '@/assets/icons/book.svg?react';
import CalendarIcon from '@/assets/icons/calender.svg?react';
import InfoIcon from '@/assets/icons/info.svg?react';
import {
  MARKET_SOURCES,
  VINTAGE_INSIGHTS,
  VINTAGE_PRICE_COMPARISON,
  VINTAGE_SDG_PREMIUM,
  type VintageInsightId,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import BandLabel from '@/components/pricing/shared/BandLabel';
import BarComparison from '@/components/pricing/shared/BarComparison';
import { toBarItems } from '@/components/pricing/shared/barItems';
import ChartPanel from '@/components/pricing/shared/ChartPanel';
import InsightRow from '@/components/pricing/shared/InsightRow';
import PanelFooter from '@/components/pricing/shared/PanelFooter';
import StatPanel from '@/components/pricing/shared/StatPanel';

const INSIGHT_ICONS: Record<VintageInsightId, React.FC<React.SVGProps<SVGSVGElement>>> = {
  reporting: CalendarIcon,
  methodology: BookIcon,
  quality: InfoIcon,
};

const VintageComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => {
  const items = toBarItems(VINTAGE_PRICE_COMPARISON);
  const chartLabel = `2024 average transaction prices: ${VINTAGE_PRICE_COMPARISON.map(
    (datum) => `${datum.label} averaged ${datum.displayValue}`,
  ).join(', ')}`;

  return (
    <>
      <ChartPanel
        activeForce="vintage"
        chart={
          <div>
            <BandLabel>2024 average transaction price</BandLabel>
            <div className="mt-4">
              <BarComparison items={items} label={chartLabel} />
            </div>
            <StatPanel stat={VINTAGE_SDG_PREMIUM} />
          </div>
        }
        asideLabel="Why buyers prefer recent vintages"
        aside={
          <div className="space-y-4">
            {VINTAGE_INSIGHTS.map((insight) => (
              <InsightRow key={insight.id} Icon={INSIGHT_ICONS[insight.id]} title={insight.title}>
                {insight.body}
              </InsightRow>
            ))}
          </div>
        }
      />
      <PanelFooter activeForce="vintage" onSelect={onForceChange} sources={MARKET_SOURCES} />
    </>
  );
};

export default VintageComparison;
