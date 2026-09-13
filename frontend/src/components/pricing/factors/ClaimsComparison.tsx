import React from 'react';
import {
  CLAIMS_LANES,
  CLAIMS_LANES_INTRO,
  CLAIMS_PRICE_OUTLOOK,
  CLAIMS_SOURCES,
  type ClaimsLane,
} from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';
import {
  DemandText,
  FlowLine,
  MethodologyChips,
  type Lane,
} from '@/components/pricing/shared/LaneComparison';
import TimelineFactorPanel from '@/components/pricing/shared/TimelineFactorPanel';

const claimsLanes = (lanes: ClaimsLane[]): Lane[] =>
  lanes.map((lane) => ({
    title: lane.title,
    tone: lane.tone,
    status: lane.status,
    sections: [
      { label: 'Role', content: <FlowLine from={lane.flow.from} to={lane.flow.to} /> },
      { label: 'How it counts', content: <DemandText>{lane.demand}</DemandText> },
      { label: 'Examples', content: <MethodologyChips items={lane.methodologies} /> },
    ],
  }));

const ClaimsComparison: React.FC<{ onForceChange: (force: ForceId) => void }> = ({ onForceChange }) => (
  <TimelineFactorPanel
    activeForce="claims"
    timelineLabel="SBTi V2.0 rollout"
    lanesLabel="What counts toward net-zero"
    lanesIntro={CLAIMS_LANES_INTRO}
    lanes={claimsLanes(CLAIMS_LANES)}
    outlooks={CLAIMS_PRICE_OUTLOOK}
    sources={CLAIMS_SOURCES}
    onForceChange={onForceChange}
  />
);

export default ClaimsComparison;
