import React from 'react';
import { FACTOR_INTRO } from '@/data/pricingFactorContent';
import { FORCES, type ForceId } from '@/data/pricingData';

/**
 * Shared factor heading: force label + intro line. Used by DataCard and
 * ChartPanel so both panel layouts render the same header block.
 */
const FactorHeader: React.FC<{ activeForce: ForceId; className?: string }> = ({ activeForce, className = '' }) => {
  const force = FORCES[activeForce];
  return (
    <header className={`max-w-3xl 3xl:max-w-4xl 4xl:max-w-5xl ${className}`}>
      <h2 className="text-balance font-poppins text-heading-2 3xl:text-2xl font-semibold tracking-tight text-text-primary">{force.label}</h2>
      <p className="mt-2 max-w-[65ch] text-pretty font-inter text-body-sm md:text-body 3xl:text-lg 4xl:text-xl text-text-secondary">{FACTOR_INTRO[activeForce]}</p>
    </header>
  );
};

export default FactorHeader;
