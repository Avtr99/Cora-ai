import React from 'react';
import type { ForceId } from '@/data/pricingData';
import TypeComparison from '@/components/pricing/factors/TypeComparison';
import IntegrityComparison from '@/components/pricing/factors/IntegrityComparison';
import ClaimsComparison from '@/components/pricing/factors/ClaimsComparison';
import ComplianceComparison from '@/components/pricing/factors/ComplianceComparison';
import VintageComparison from '@/components/pricing/factors/VintageComparison';

// ---------------------------------------------------------------------------
// Each factor renders as one white learning surface with open evidence and
// explanation bands. The footer and price outlook cards sit outside on the
// page background. Shared primitives live in ./shared, per-factor panels in
// ./factors.
//
// Spacing rhythm: compact label groups inside generous section spacing,
// with layout gaps rather than repeated divider rules.
// ---------------------------------------------------------------------------

interface FactorComparisonProps {
  activeForce: ForceId;
  onForceChange: (force: ForceId) => void;
}

type FactorPanel = React.FC<{ onForceChange: (force: ForceId) => void }>;

/** Exhaustive by construction - a missing ForceId key is a compile error. */
const FACTOR_PANELS: Record<ForceId, FactorPanel> = {
  type: TypeComparison,
  integrity: IntegrityComparison,
  claims: ClaimsComparison,
  compliance: ComplianceComparison,
  vintage: VintageComparison,
};

const FactorComparison: React.FC<FactorComparisonProps> = ({ activeForce, onForceChange }) => {
  const Panel = FACTOR_PANELS[activeForce];
  return <Panel onForceChange={onForceChange} />;
};

export default FactorComparison;
