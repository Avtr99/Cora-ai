import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { TONE_CLASSES } from '@/components/pricing/shared/barItems';
import type { Caption, VerticalBarStep } from '@/data/pricingFactorContent';

const gap = 'gap-3 3xl:gap-4';

/**
 * Caption under a visual: bolded lead-in plus trailing text.
 */
export const VisualCaption: React.FC<{ caption: Caption }> = ({ caption }) => (
  <p className="mt-2.5 font-inter text-caption 3xl:text-ui leading-relaxed text-text-muted">
    {caption.lead}
    {caption.strong ? <b className="font-semibold text-text-primary">{caption.strong}</b> : null}
    {caption.tail}
  </p>
);

/**
 * Vertical bars on a shared scale with an optional labelled divider between
 * two columns (an event such as a methodology approval). The tallest bar sets
 * the scale; labels sit above their bar.
 */
const VerticalBars: React.FC<{
  steps: VerticalBarStep[];
  height?: number;
  label?: string;
  caption?: Caption;
}> = ({ steps, height = 140, label, caption }) => {
  const reduceMotion = useReducedMotion();
  const bars = steps.filter((step): step is Extract<VerticalBarStep, { kind: 'bar' }> => step.kind === 'bar');
  const maximum = Math.max(...bars.map((bar) => bar.value));

  return (
    <div role={label ? 'img' : undefined} aria-label={label}>
      <div className={`flex items-end ${gap} border-b border-border-strong`} style={{ height }}>
        {steps.map((step, index) => {
          if (step.kind === 'divider') {
            return (
              <div key={step.text} className="relative w-0 flex-none self-stretch border-l border-dashed border-text-primary">
                <span className="absolute top-0 left-0 -translate-x-1/2 bg-surface-card px-1.5 font-inter text-overline font-semibold whitespace-nowrap text-text-primary">
                  {step.text}
                </span>
              </div>
            );
          }
          const topClassName = step.mutedTop
            ? 'font-inter text-caption font-medium text-text-muted'
            : 'font-poppins text-body-sm 3xl:text-base font-semibold';
          const topColor = step.mutedTop || !step.top ? '' : 'text-semantic-success-text';
          return (
            <div key={step.label} className="flex h-full min-w-0 flex-1 flex-col items-center justify-end">
              <span className={`${topClassName} ${topColor} mb-1.5 whitespace-nowrap tabular-nums`}>
                {step.top}
                {step.delta ? (
                  <span className="ml-1.5 font-inter text-caption font-semibold text-semantic-success-text">
                    {step.delta}
                  </span>
                ) : null}
              </span>
              <motion.div
                className={`w-full max-w-[72px] origin-bottom rounded-t-md ${TONE_CLASSES[step.tone]}`}
                style={{ height: `calc((100% - 26px) * ${step.value / maximum})` }}
                initial={reduceMotion ? false : { scaleY: 0 }}
                animate={{ scaleY: 1 }}
                transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 0.1 + index * 0.15 }}
              />
            </div>
          );
        })}
      </div>
      <div className={`mt-2 flex ${gap}`}>
        {steps.map((step) =>
          step.kind === 'divider' ? (
            <span key={step.text} className="w-0 flex-none" />
          ) : (
            <span key={step.label} className="min-w-0 flex-1 text-center font-inter text-caption text-text-muted">
              {step.label}
            </span>
          ),
        )}
      </div>
      {caption ? <VisualCaption caption={caption} /> : null}
    </div>
  );
};

export default VerticalBars;
