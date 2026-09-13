import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { FORCES, type TimelineForceId } from '@/data/pricingData';
import { TIMELINE_COPY } from '@/data/pricingFactorContent';
import { KPI, NEUTRAL, SEMANTIC } from '@/lib/colors';

const MilestoneTimeline: React.FC<{ forceId: TimelineForceId }> = ({ forceId }) => {
  const reduceMotion = useReducedMotion();
  const timeline = FORCES[forceId].timeline;
  const copy = TIMELINE_COPY[forceId];
  const milestones = [
    { date: timeline.start, label: timeline.startLabel, active: false, future: false },
    { date: timeline.middle, label: timeline.middleLabel, active: true, future: false },
    { date: timeline.end, label: timeline.endLabel, active: false, future: true },
  ];

  return (
    <>
      <div className="relative" role="img" aria-label={copy.ariaLabel}>
        <span aria-hidden="true" className="absolute left-2 right-2 top-3.5 h-1 overflow-hidden rounded-full bg-border-strong">
          <span aria-hidden="true" className="block h-full w-1/2 rounded-full bg-kpi-removal" />
        </span>
        <div className="grid grid-cols-3 gap-4">
          {milestones.map((milestone, index) => {
            const alignment =
              index === 0 ? 'items-start text-left' : index === 2 ? 'items-end text-right' : 'items-center text-center';
            const copyAlignment = index === 0 ? 'items-start' : index === 2 ? 'items-end' : 'items-center';
            return (
              <div key={milestone.date} className={`flex min-w-0 flex-col ${alignment}`}>
                <motion.span
                  className="relative mt-2 block h-4 w-4 rounded-full"
                  style={{
                    backgroundColor: milestone.active || milestone.future ? KPI.removal : NEUTRAL[300],
                    boxShadow: milestone.active ? `0 0 0 4px ${SEMANTIC.success.border}` : undefined,
                  }}
                  initial={reduceMotion ? false : { scale: 0.5, opacity: 0 }}
                  animate={{ scale: 1, opacity: 1 }}
                  transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1], delay: 0.1 + index * 0.08 }}
                />
                <div
                  className={`mt-3 flex min-w-0 flex-col gap-y-0.5 sm:flex-row sm:flex-wrap sm:items-baseline sm:gap-x-2 ${copyAlignment}`}
                >
                  <span
                    className={`font-poppins text-ui 3xl:text-body font-semibold tabular-nums ${
                      milestone.active ? 'text-semantic-success-text' : 'text-text-primary'
                    }`}
                  >
                    {milestone.date}
                  </span>
                  <span className="font-inter text-ui 3xl:text-sm 4xl:text-base text-text-secondary">
                    {milestone.label}
                  </span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <p className="mt-7 max-w-[78ch] font-inter text-ui 3xl:text-sm 4xl:text-base leading-relaxed text-text-secondary">{copy.note}</p>
    </>
  );
};

export default MilestoneTimeline;
