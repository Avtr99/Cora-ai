import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { TrendingDown, TrendingUp } from 'lucide-react';
import { TONE_CLASSES, type BarDatum } from '@/components/pricing/shared/barItems';

const GRID =
  'grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-2 sm:grid-cols-[12.5rem_minmax(0,1fr)_8.25rem] sm:gap-x-6 3xl:grid-cols-[13rem_minmax(0,1fr)_9rem] 4xl:grid-cols-[15rem_minmax(0,1fr)_10rem]';

/**
 * Price comparison on a linear scale: name and examples, a proportional track,
 * then the price with an optional ratio caption or year-on-year chip. The axis
 * sits outside the group so the group holds exactly one styled node per bar.
 */
const BarComparison: React.FC<{
  items: BarDatum[];
  label: string;
  hint?: string;
  /** Caption family for the ratio under each price, e.g. `reduction`. */
  ratioSuffix?: string;
  axis?: { ticks: number[]; max: number };
  legend?: React.ReactNode;
}> = ({ items, label, hint, ratioSuffix, axis, legend }) => {
  const reduceMotion = useReducedMotion();
  // The first datum is the ratio reference - its caption reads "Baseline".
  const baseline = items[0];

  return (
    <div>
      {hint ? (
        <p className="max-w-[56ch] text-pretty font-inter text-ui 3xl:text-sm 4xl:text-base leading-relaxed text-text-secondary">
          {hint}
        </p>
      ) : null}
      <div role="group" aria-label={label} className="mt-5 grid gap-4 3xl:gap-5">
        {items.map((item, index) => {
          const ChipIcon = item.chip?.direction === 'down' ? TrendingDown : TrendingUp;
          return (
            <div key={item.label} className={GRID}>
              <div className="col-span-2 min-w-0 sm:col-span-1">
                <b className="flex items-center gap-2 font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-semibold leading-tight text-text-primary">
                  <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${TONE_CLASSES[item.tone]}`} />
                  {item.label}
                </b>
                {item.examples ? (
                  <small className="mt-0.5 block pl-4 font-inter text-caption 3xl:text-ui leading-snug text-text-muted">
                    {item.examples}
                  </small>
                ) : null}
              </div>
              <div className="h-[26px] min-w-0 rounded-md bg-surface-base 3xl:h-8 4xl:h-9">
                <motion.div
                  className={`h-full min-w-[6px] origin-left rounded-md ${TONE_CLASSES[item.tone]}`}
                  style={{ width: `${item.widthPct}%` }}
                  initial={reduceMotion ? false : { scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.1 + index * 0.12 }}
                />
              </div>
              <div className="col-span-2 text-right sm:col-span-1">
                <b className="block font-poppins text-lg sm:text-xl 3xl:text-2xl 4xl:text-3xl font-semibold leading-none tracking-tight text-text-primary tabular-nums">
                  {item.value}
                </b>
                {ratioSuffix ? (
                  <small className="mt-1.5 block font-inter text-caption 3xl:text-ui leading-snug text-text-muted tabular-nums">
                    {index === 0
                      ? 'Baseline'
                      : `${(item.rawValue / baseline.rawValue).toFixed(1)}\u00d7${item.open || item.chip ? '+' : ''} ${ratioSuffix}`}
                  </small>
                ) : null}
                {item.chip ? (
                  <span
                    className={`mt-1.5 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 font-inter text-caption 3xl:text-ui font-semibold tabular-nums ${
                      item.chip.direction === 'down'
                        ? 'bg-kpi-reduction-bg text-kpi-reduction'
                        : 'bg-semantic-success-bg text-semantic-success-text'
                    }`}
                  >
                    <ChipIcon aria-hidden="true" strokeWidth={2.5} className="h-3.5 w-3.5" />
                    {item.chip.text}
                  </span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
      {axis ? (
        <div aria-hidden="true" className={`mt-2 ${GRID}`}>
          <div className="hidden sm:block" />
          <div className="relative h-4">
            {axis.ticks.map((tick, tickIndex) => (
              <span
                key={tick}
                className={`absolute top-0 font-inter text-overline text-text-muted tabular-nums ${
                  tickIndex === 0
                    ? 'translate-x-0'
                    : tickIndex === axis.ticks.length - 1
                      ? '-translate-x-full'
                      : '-translate-x-1/2'
                }`}
                style={{ left: `${(tick / axis.max) * 100}%` }}
              >
                ${tick}
              </span>
            ))}
          </div>
          <div className="hidden sm:block" />
        </div>
      ) : null}
      {legend ? (
        <p className="mt-4 border-t border-border-ui pt-4 font-inter text-caption 3xl:text-ui leading-relaxed text-text-muted">
          {legend}
        </p>
      ) : null}
    </div>
  );
};

export default BarComparison;
