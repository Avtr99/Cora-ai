import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import type { WaffleVis } from '@/data/pricingFactorContent';

/**
 * One hundred cells, `on` of them colored: a share of a whole you can count.
 * Cells fill left to right with a short stagger so the count reads as a fill,
 * not as a static block.
 */
const Waffle: React.FC<{ vis: WaffleVis }> = ({ vis }) => {
  const reduceMotion = useReducedMotion();
  return (
    <div aria-hidden="true" className="grid grid-cols-20 gap-[3px]">
      {Array.from({ length: vis.total }, (_, index) => (
        <motion.span
          key={index}
          className={`aspect-square rounded-xs ${index < vis.on ? 'bg-kpi-removal' : 'bg-border-ui'}`}
          initial={reduceMotion || index >= vis.on ? false : { scale: 0, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1], delay: 0.3 + index * 0.06 }}
        />
      ))}
    </div>
  );
};

export default Waffle;
