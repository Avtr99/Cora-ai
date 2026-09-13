import React from 'react';
import BookIcon from '@/assets/icons/book.svg?react';
import LightbulbIcon from '@/assets/icons/lightbulb.svg?react';
import TreeIcon from '@/assets/icons/tree.svg?react';
import {
  MARKET_SOURCES,
  TYPE_INSIGHTS,
  TYPE_PRICE_COMPARISON,
  type TypeInsightId,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import BandLabel from '@/components/pricing/shared/BandLabel';
import BarComparison from '@/components/pricing/shared/BarComparison';
import { toBarItems } from '@/components/pricing/shared/barItems';
import ChartPanel from '@/components/pricing/shared/ChartPanel';
import InsightRow from '@/components/pricing/shared/InsightRow';
import PanelFooter from '@/components/pricing/shared/PanelFooter';

const INSIGHT_ICONS: Record<TypeInsightId, React.FC<React.SVGProps<SVGSVGElement>>> = {
  supply: TreeIcon,
  demand: LightbulbIcon,
  durability: BookIcon,
};

const TypeComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => {
  const items = toBarItems(TYPE_PRICE_COMPARISON);
  const chartLabel = `2024 average transaction prices: ${TYPE_PRICE_COMPARISON.map(
    (datum) => `${datum.label} averaged ${datum.displayValue}`,
  ).join(', ')}`;

  return (
    <>
      <ChartPanel
        activeForce="type"
        chart={
          <div>
            <BandLabel>2024 average transaction price</BandLabel>
            <div className="mt-4">
              <BarComparison items={items} label={chartLabel} />
            </div>
          </div>
        }
        asideLabel="Why the gap exists"
        aside={
          <div className="space-y-4">
            {TYPE_INSIGHTS.map((insight) => (
              <InsightRow key={insight.id} Icon={INSIGHT_ICONS[insight.id]} title={insight.title}>
                {insight.body}
              </InsightRow>
            ))}
          </div>
        }
      />
      <PanelFooter activeForce="type" onSelect={onForceChange} sources={MARKET_SOURCES} />
    </>
  );
};

export default TypeComparison;
