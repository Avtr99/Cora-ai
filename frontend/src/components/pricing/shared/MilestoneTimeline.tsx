import React from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import {
  FORCES,
  type TimelineBarTone,
  type TimelineForceId,
  type TimelineMilestone,
} from '@/data/pricingData';
import { TIMELINE_COPY } from '@/data/pricingFactorContent';
import { fractionalYear, monthsUntil } from '@/components/pricing/shared/today';

const BAR_TONE_CLASSES: Record<TimelineBarTone, string> = {
  muted: 'bg-surface-subtle text-text-secondary',
  base: 'bg-surface-muted text-text-primary',
  green: 'bg-kpi-removal-soft text-semantic-success-text',
  hatch: 'text-text-primary',
};

/** Patterns are drawn inline; every flat color comes from a theme token. */
const HATCH_INK = 'color-mix(in srgb, var(--color-text-primary) 28%, transparent)';
const barStyle = (tone: TimelineBarTone): React.CSSProperties =>
  tone === 'hatch'
    ? {
        backgroundImage: `repeating-linear-gradient(135deg, ${HATCH_INK} 0 1.5px, transparent 1.5px 6px)`,
        boxShadow: `inset 0 0 0 1px ${HATCH_INK}`,
      }
    : {};

type MilestoneState = 'past' | 'next' | 'future';

const stateOf = (milestone: TimelineMilestone, today: number, nextId?: number): MilestoneState =>
  milestone.at <= today ? 'past' : milestone.id === nextId ? 'next' : 'future';

const statusOf = (state: MilestoneState, at: number): string =>
  state === 'past' ? 'Passed' : state === 'next' ? `In ${monthsUntil(at)} months` : 'Ahead';

/**
 * Proportional timeline: a labelled year axis, phase bars positioned on it,
 * a today line, and milestone cards below that light up their diamond on
 * hover. The grid is a labelled image for screen readers; the cards carry the
 * readable text.
 */
const MilestoneTimeline: React.FC<{ forceId: TimelineForceId }> = ({ forceId }) => {
  const reduceMotion = useReducedMotion();
  const timeline = FORCES[forceId].timeline;
  const copy = TIMELINE_COPY[forceId];

  const now = new Date();
  const today = fractionalYear(now);
  const todayLabel = now.toLocaleDateString('en-GB', { month: 'short', year: 'numeric' });

  const span = timeline.to - timeline.from;
  const x = (value: number) => ((value - timeline.from) / span) * 100;
  const years = Array.from({ length: span }, (_, index) => timeline.from + index);
  const nextId = timeline.milestones.find((milestone) => milestone.at > today)?.id;
  const inRange = today >= timeline.from && today < timeline.to;
  const trackBackground = `repeating-linear-gradient(90deg, var(--color-border-ui) 0 1px, transparent 1px calc(100% / ${years.length}))`;

  return (
    <>
      <div
        className="grid grid-cols-[4rem_minmax(0,1fr)] gap-x-2.5 gap-y-2.5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:gap-x-5 3xl:gap-y-3"
        role="img"
        aria-label={copy.ariaLabel}
      >
        {/* Year axis */}
        <div className="relative col-start-2 row-start-1 h-6">
          {years.map((year, index) => {
            const isNow = inRange && Math.floor(today) === year;
            return (
              <span
                key={year}
                className={`absolute top-0 -translate-x-1/2 font-inter text-overline tabular-nums ${
                  isNow ? 'font-semibold text-text-primary' : 'text-text-muted'
                } ${!isNow && index % 2 === 1 ? 'hidden sm:block' : ''}`}
                style={{ left: `${x(year + 0.5)}%` }}
              >
                {year}
              </span>
            );
          })}
        </div>

        {timeline.rows.map((row, rowIndex) => (
          <React.Fragment key={row.name}>
            <p
              className="col-start-1 self-center font-poppins text-caption 3xl:text-ui font-semibold leading-snug text-text-primary sm:text-body-sm"
              style={{ gridRow: rowIndex + 2 }}
            >
              {row.name}
              <small className="mt-0.5 block font-inter text-overline font-medium text-text-muted">{row.sub}</small>
            </p>
            <div
              className="col-start-2 relative h-12"
              style={{ gridRow: rowIndex + 2, backgroundImage: trackBackground, boxShadow: 'inset -1px 0 0 var(--color-border-ui)' }}
            >
              {row.bars.map((bar, barIndex) => (
                <motion.span
                  key={`${bar.from}-${bar.to}`}
                  className={`absolute top-1.5 bottom-1.5 flex items-center overflow-hidden rounded-md pr-3 pl-4 font-inter text-caption font-semibold whitespace-nowrap ${
                    BAR_TONE_CLASSES[bar.tone]
                  } ${bar.open ? 'rounded-r-none [mask-image:linear-gradient(90deg,#000_86%,transparent)]' : ''}`}
                  style={{ ...barStyle(bar.tone), left: `${x(bar.from)}%`, width: `${x(bar.to) - x(bar.from)}%` }}
                  initial={reduceMotion ? false : { clipPath: 'inset(0 100% 0 0)' }}
                  animate={{ clipPath: 'inset(0 0% 0 0)' }}
                  transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1], delay: 0.1 + rowIndex * 0.15 + barIndex * 0.3 }}
                >
                  {bar.text}
                </motion.span>
              ))}
              {(row.milestones ?? []).map((milestoneId) => {
                const milestone = timeline.milestones[milestoneId];
                const state = stateOf(milestone, today, nextId);
                return (
                  <span
                    key={milestoneId}
                    aria-hidden="true"
                    className={`absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rotate-45 rounded-[2px] border-2 ${
                      state === 'past'
                        ? 'border-text-muted bg-text-muted'
                        : state === 'next'
                          ? 'border-text-primary bg-surface-inverse'
                          : 'border-text-primary bg-surface-card'
                    }`}
                    style={{ left: `${x(milestone.at)}%` }}
                  />
                );
              })}
              {row.tag ? (
                <span
                  className={`absolute top-1/2 translate-x-4 -translate-y-1/2 font-inter text-caption whitespace-nowrap ${
                    row.tag.soft ? 'font-medium text-text-muted' : 'font-semibold text-text-primary'
                  }`}
                  style={{ left: `${x(row.tag.at)}%` }}
                >
                  {row.tag.text}
                </span>
              ) : null}
            </div>
          </React.Fragment>
        ))}

        {inRange ? (
          <>
            <div className="col-start-2 h-6" style={{ gridRow: timeline.rows.length + 2 }} />
            <motion.div
              aria-hidden="true"
              className="pointer-events-none relative col-start-2"
              style={{ gridRow: `1 / ${timeline.rows.length + 3}` }}
              initial={reduceMotion ? false : { opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1], delay: 1.1 }}
            >
              <span
                className="absolute top-6 bottom-6 border-l-[1.5px] border-text-primary"
                style={{ left: `${x(today)}%` }}
              />
              <span
                className="absolute bottom-0 -translate-x-1/2 rounded-md bg-surface-inverse px-2 py-1 font-inter text-overline font-semibold whitespace-nowrap text-text-inverse tabular-nums"
                style={{ left: `${x(today)}%` }}
              >
                Today &middot; {todayLabel}
              </span>
            </motion.div>
          </>
        ) : null}
      </div>

      <ol className="mt-3 grid grid-cols-1 border-t border-border-ui sm:grid-cols-3">
        {timeline.milestones.map((milestone, index) => {
          const state = stateOf(milestone, today, nextId);
          return (
            <li
              key={milestone.id}
              className={`min-w-0 p-4 3xl:p-5 ${index > 0 ? 'border-t border-border-ui sm:border-t-0 sm:border-l sm:border-border-ui' : 'sm:pr-5'}`}
            >
              <div className="flex items-center justify-between gap-2">
                <p className="flex items-baseline gap-2 font-poppins text-body 3xl:text-lg font-semibold tracking-tight tabular-nums">
                  <span className={state === 'past' ? 'text-text-muted' : 'text-text-primary'}>{milestone.date}</span>
                  <span className="font-inter text-overline font-semibold uppercase tracking-wider text-text-muted">
                    {milestone.era}
                  </span>
                </p>
                <span
                  className={`flex-none rounded-md px-2 py-0.5 font-inter text-overline font-semibold tabular-nums ${
                    state === 'next' ? 'bg-surface-inverse text-text-inverse' : 'bg-surface-subtle text-text-secondary'
                  }`}
                >
                  {statusOf(state, milestone.at)}
                </span>
              </div>
              <p className="mt-1.5 text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
                {milestone.label}
              </p>
            </li>
          );
        })}
      </ol>
    </>
  );
};

export default MilestoneTimeline;
