import React from 'react';
import type { ForceId } from '@/data/pricingData';
import FactorHeader from '@/components/pricing/shared/FactorHeader';

const DataCard: React.FC<{ activeForce: ForceId; children: React.ReactNode }> = ({ activeForce, children }) => (
  <article>
    <FactorHeader activeForce={activeForce} className="mb-6" />
    {children}
  </article>
);

export default DataCard;
