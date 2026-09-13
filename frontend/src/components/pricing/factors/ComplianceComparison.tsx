import React from 'react';
import {
  COMPLIANCE_BUYER_POOLS,
  COMPLIANCE_PRICE_OUTLOOK,
  COMPLIANCE_SOURCES,
  type BuyerPool,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import {
  BulletList,
  DemandText,
  type Lane,
} from '@/components/pricing/shared/LaneComparison';
import TimelineFactorPanel from '@/components/pricing/shared/TimelineFactorPanel';

const complianceLanes = (pools: BuyerPool[]): Lane[] =>
  pools.map((pool) => ({
    title: pool.title,
    tone: pool.tone,
    status: pool.status,
    sections: [
      { label: 'Demand', content: <DemandText>{pool.body}</DemandText> },
      { label: 'Buyer pools', content: <BulletList items={pool.buyers} /> },
    ],
  }));

const ComplianceComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => (
  <TimelineFactorPanel
    activeForce="compliance"
    timelineLabel="CORSIA demand deadline"
    lanesLabel="Who can buy the credit"
    lanes={complianceLanes(COMPLIANCE_BUYER_POOLS)}
    outlooks={COMPLIANCE_PRICE_OUTLOOK}
    sources={COMPLIANCE_SOURCES}
    onForceChange={onForceChange}
  />
);

export default ComplianceComparison;
