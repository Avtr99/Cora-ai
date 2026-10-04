import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { TONE_CLASSES } from '@/components/pricing/shared/barItems';
import type { MiniBarRow } from '@/data/pricingFactorContent';

/**
 * Mini horizontal bars: label, optional tag, a proportional track and the
 * number at the end. `max` fixes the scale (a percentage chart passes 100);
 * without it the largest row fills the track.
 */
const MiniBars: React.FC<{ rows: MiniBarRow[]; max?: number; label?: string }> = ({
  rows,
  max,
  label,
}) => {
  const reduceMotion = useReducedMotion();
  const scale = max ?? Math.max(...rows.map((row) => row.value));

  return (
    <div role={label ? 'img' : undefined} aria-label={label} className="grid gap-3.5 3xl:gap-4">
      {rows.map((row, index) => (
        <div key={row.key} className="grid grid-cols-[minmax(0,1fr)_auto] items-baseline gap-x-3 gap-y-1.5">
          <span className="min-w-0 font-inter text-ui 3xl:text-sm 4xl:text-base font-semibold text-text-primary">
            {row.key}
            {row.sub ? <small className="ml-1.5 font-medium text-text-muted">{row.sub}</small> : null}
          </span>
          <span className="justify-self-end font-inter text-caption text-text-muted">{row.tag}</span>
          <div className="col-span-2 grid grid-cols-[minmax(0,1fr)_3.5rem] items-center gap-x-2.5">
            <span className="block h-2.5 overflow-hidden rounded-sm bg-surface-subtle">
              <motion.span
                className={`block h-full origin-left rounded-sm ${TONE_CLASSES[row.tone]}`}
                style={{ width: `${(row.value / scale) * 100}%` }}
                initial={reduceMotion ? false : { scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.15 + index * 0.15 }}
              />
            </span>
            <b className="text-right font-inter text-ui 3xl:text-sm 4xl:text-base font-semibold text-text-primary tabular-nums">
              {row.display}
            </b>
          </div>
        </div>
      ))}
    </div>
  );
};

export default MiniBars;
