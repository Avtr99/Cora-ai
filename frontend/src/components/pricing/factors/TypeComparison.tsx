import React from 'react';
import {
  MARKET_SOURCES,
  TYPE_DEMAND_CAPTION,
  TYPE_DEMAND_VIS,
  TYPE_DURABILITY_CAPTION,
  TYPE_DURABILITY_VIS,
  TYPE_INSIGHTS,
  TYPE_PRICE_ARIA_LABEL,
  TYPE_PRICE_AXIS,
  TYPE_PRICE_COMPARISON,
  TYPE_PRICE_HINT,
  TYPE_SUPPLY_WAFFLE,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import Band from '@/components/pricing/shared/Band';
import BarComparison from '@/components/pricing/shared/BarComparison';
import { toBarItems } from '@/components/pricing/shared/barItems';
import DataCard from '@/components/pricing/shared/DataCard';
import MiniBars from '@/components/pricing/shared/MiniBars';
import PanelFooter from '@/components/pricing/shared/PanelFooter';
import VerticalBars, { VisualCaption } from '@/components/pricing/shared/VerticalBars';
import Waffle from '@/components/pricing/shared/Waffle';

/**
 * One cell of the three-up evidence row: heading, explanation, then the
 * visual pinned to the bottom of the cell with its caption.
 */
const EvidenceCell: React.FC<{
  title: string;
  body: string;
  caption?: React.ReactNode;
  children: React.ReactNode;
}> = ({ title, body, caption, children }) => (
  <section className="flex min-w-0 flex-col p-5 3xl:p-6 4xl:p-7 sm:p-6">
    <h4 className="font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-semibold leading-snug text-text-primary">
      {title}
    </h4>
    <p className="mt-1.5 text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">{body}</p>
    <div className="mt-auto pt-6">{children}</div>
    {caption}
  </section>
);

const TypeComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => {
  const items = toBarItems(TYPE_PRICE_COMPARISON);
  const [supply, demand, durability] = TYPE_INSIGHTS;

  return (
    <>
      <DataCard activeForce="type">
        <Band first label="2024 average transaction price">
          <BarComparison
            items={items}
            label={TYPE_PRICE_ARIA_LABEL}
            hint={TYPE_PRICE_HINT}
            ratioSuffix="reduction"
            axis={{ ticks: TYPE_PRICE_AXIS, max: TYPE_PRICE_AXIS[TYPE_PRICE_AXIS.length - 1] }}
          />
        </Band>
        <Band label="Why the gap exists" bare>
          <div className="grid grid-cols-1 divide-y divide-border-ui md:grid-cols-3 md:divide-x md:divide-y-0">
            <EvidenceCell title={supply.title} body={supply.body} caption={<VisualCaption caption={TYPE_SUPPLY_WAFFLE.caption} />}>
              <Waffle vis={TYPE_SUPPLY_WAFFLE} />
            </EvidenceCell>
            <EvidenceCell
              title={demand.title}
              body={demand.body}
            >
              <VerticalBars steps={TYPE_DEMAND_VIS} height={120} caption={TYPE_DEMAND_CAPTION} />
            </EvidenceCell>
            <EvidenceCell
              title={durability.title}
              body={durability.body}
              caption={<VisualCaption caption={{ tail: TYPE_DURABILITY_CAPTION }} />}
            >
              <MiniBars rows={TYPE_DURABILITY_VIS} />
            </EvidenceCell>
          </div>
        </Band>
      </DataCard>
      <PanelFooter activeForce="type" onSelect={onForceChange} sources={MARKET_SOURCES} />
    </>
  );
};

export default TypeComparison;
