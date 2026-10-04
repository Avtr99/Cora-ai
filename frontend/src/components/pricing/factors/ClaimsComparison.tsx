import React from 'react';
import {
  CLAIMS_FLOW_INTRO,
  CLAIMS_PRICE_OUTLOOK,
  CLAIMS_SOURCES,
  CLAIMS_TIMELINE_NOTE,
  NET_ZERO_BAND_SUB,
  TIMELINE_COPY,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import Band from '@/components/pricing/shared/Band';
import ClaimFlow from '@/components/pricing/shared/ClaimFlow';
import DataCard from '@/components/pricing/shared/DataCard';
import MilestoneTimeline from '@/components/pricing/shared/MilestoneTimeline';
import NetZeroChart from '@/components/pricing/shared/NetZeroChart';
import OutlookCards from '@/components/pricing/shared/OutlookCards';
import PanelFooter from '@/components/pricing/shared/PanelFooter';

const TimelineNote: React.FC<{ children: string }> = ({ children }) => (
  <p className="mt-4 max-w-[78ch] text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
    {children}
  </p>
);

const ClaimsComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => (
  <>
    <DataCard activeForce="claims">
      <Band first label="The net-zero equation" sub={NET_ZERO_BAND_SUB}>
        <NetZeroChart />
      </Band>
      <Band label="SBTi V2.0 rollout">
        <MilestoneTimeline forceId="claims" />
      </Band>
      <TimelineNote>{CLAIMS_TIMELINE_NOTE}</TimelineNote>
      <Band label="What counts toward net-zero">
        <p className="max-w-[70ch] text-pretty font-inter text-ui 3xl:text-sm 4xl:text-base leading-relaxed text-text-muted">
          {CLAIMS_FLOW_INTRO}
        </p>
        <div className="mt-6">
          <ClaimFlow />
        </div>
      </Band>
    </DataCard>
    <OutlookCards outlooks={CLAIMS_PRICE_OUTLOOK} />
    <PanelFooter activeForce="claims" onSelect={onForceChange} sources={CLAIMS_SOURCES} />
  </>
);

export default ClaimsComparison;
