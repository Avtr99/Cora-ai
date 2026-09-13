import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { TONE_COLORS, type BarDatum } from '@/components/pricing/shared/barItems';

const BarComparison: React.FC<{
  items: BarDatum[];
  label: string;
  valueClassName?: string;
}> = ({
  items,
  label,
  valueClassName = 'text-right font-inter text-lg sm:text-xl font-semibold tracking-tight text-text-primary tabular-nums',
}) => {
  const reduceMotion = useReducedMotion();
  return (
    <div role="group" aria-label={label} className="space-y-5 sm:space-y-6">
      {items.map((item, index) => (
        <div key={item.label} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-5 gap-y-3 py-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_6rem] sm:gap-4">
          <span className="font-inter text-body-sm sm:text-body 3xl:text-lg 4xl:text-xl font-medium text-text-primary">{item.label}</span>
          <div className="order-last col-span-2 h-2.5 3xl:h-3 4xl:h-3.5 rounded-full bg-surface-subtle sm:order-none sm:col-span-1">
            <motion.div
              className="h-full min-w-2 rounded-full"
              style={{ backgroundColor: TONE_COLORS[item.tone], width: `${Math.max(item.widthPct, 6)}%`, transformOrigin: 'left center' }}
              initial={reduceMotion ? false : { scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.45, ease: [0.4, 0, 0.2, 1], delay: 0.1 + index * 0.07 }}
            />
          </div>
          <span className={valueClassName}>{item.value}</span>
        </div>
      ))}
    </div>
  );
};

export default BarComparison;
