import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import FactorComparison from '@/components/pricing/FactorComparison';
import type { ForceId } from '@/data/pricingData';

interface PricingExplorerProps {
  activeForce: ForceId;
  onForceChange: (force: ForceId) => void;
}

const PricingExplorer: React.FC<PricingExplorerProps> = ({ activeForce, onForceChange }) => {
  const reduceMotion = useReducedMotion();

  return (
    <section
      id="pricing-panel"
      role="tabpanel"
      aria-labelledby={`pricing-tab-${activeForce}`}
      tabIndex={0}
      className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-4"
    >
      <motion.div
        key={activeForce}
        initial={reduceMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
      >
        <FactorComparison activeForce={activeForce} onForceChange={onForceChange} />
      </motion.div>
    </section>
  );
};

export default PricingExplorer;
