import React from 'react';
import type { PricingSource, PriceOutlook } from '@/data/pricingFactorContent';
import type { ForceId, TimelineForceId } from '@/data/pricingData';
import BandLabel from '@/components/pricing/shared/BandLabel';
import DataCard from '@/components/pricing/shared/DataCard';
import LaneComparison, { type Lane } from '@/components/pricing/shared/LaneComparison';
import MilestoneTimeline from '@/components/pricing/shared/MilestoneTimeline';
import OutlookCards from '@/components/pricing/shared/OutlookCards';
import PanelFooter from '@/components/pricing/shared/PanelFooter';

/**
 * Panel layout for the timeline factors (claims, compliance): label + timeline,
 * then label + lane comparison, then outlook cards and the footer. Accepts
 * TimelineForceId so only timeline-bearing factors can use it.
 */
const TimelineFactorPanel: React.FC<{
  activeForce: TimelineForceId;
  timelineLabel: string;
  lanesLabel: string;
  lanesIntro?: string;
  lanes: Lane[];
  outlooks: PriceOutlook[];
  sources: PricingSource[];
  onForceChange: (force: ForceId) => void;
}> = ({ activeForce, timelineLabel, lanesLabel, lanesIntro, lanes, outlooks, sources, onForceChange }) => (
  <>
    <DataCard activeForce={activeForce}>
      <div>
        <BandLabel>{timelineLabel}</BandLabel>
        <div className="mt-4">
          <MilestoneTimeline forceId={activeForce} />
        </div>
      </div>
      <div className="mt-12">
        <BandLabel>{lanesLabel}</BandLabel>
        {lanesIntro ? (
          <p className="mt-2 max-w-[70ch] text-pretty font-inter text-ui 3xl:text-sm 4xl:text-base leading-relaxed text-text-muted">
            {lanesIntro}
          </p>
        ) : null}
        <div className="mt-4">
          <LaneComparison lanes={lanes} />
        </div>
      </div>
    </DataCard>
    <OutlookCards outlooks={outlooks} />
    <PanelFooter activeForce={activeForce} onSelect={onForceChange} sources={sources} />
  </>
);

export default TimelineFactorPanel;
