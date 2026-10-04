import React from 'react';
import {
  COMPLIANCE_PRICE_OUTLOOK,
  COMPLIANCE_SOURCES,
  COMPLIANCE_STAIR_SUB,
  COMPLIANCE_STAIRCASE,
  CORSIA_DEADLINE_PHRASES,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import Band from '@/components/pricing/shared/Band';
import BuyerStaircase from '@/components/pricing/shared/BuyerStaircase';
import DataCard from '@/components/pricing/shared/DataCard';
import MilestoneTimeline from '@/components/pricing/shared/MilestoneTimeline';
import OutlookCards from '@/components/pricing/shared/OutlookCards';
import PanelFooter from '@/components/pricing/shared/PanelFooter';
import { monthsUntil } from '@/components/pricing/shared/today';

const ComplianceComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => {
  const months = monthsUntil(2028);
  return (
    <>
      <DataCard activeForce="compliance">
        <Band first label="Who can buy the credit" sub={COMPLIANCE_STAIR_SUB}>
          <BuyerStaircase />
        </Band>
        <Band label="CORSIA demand deadline">
          <MilestoneTimeline forceId="compliance" />
        </Band>
        <p className="mt-4 max-w-[78ch] text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
          {months > 0 ? CORSIA_DEADLINE_PHRASES.remaining(months) : CORSIA_DEADLINE_PHRASES.passed}
        </p>
      </DataCard>
      <OutlookCards outlooks={COMPLIANCE_PRICE_OUTLOOK} />
      <PanelFooter activeForce="compliance" onSelect={onForceChange} sources={COMPLIANCE_SOURCES} />
    </>
  );
};

export default ComplianceComparison;
