import React, { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { KPI, NEUTRAL, TEXT } from '@/lib/colors';
import { NET_ZERO_CHART_LABEL, NET_ZERO_KEYS } from '@/data/pricingFactorContent';

type ZoneId = keyof typeof NET_ZERO_KEYS;
const ZONE_IDS: ZoneId[] = ['1', '2', '3'];

const STATUS_DOT: Record<'success' | 'warning', string> = {
  success: 'bg-kpi-removal',
  warning: 'bg-kpi-reduction',
};

/**
 * The net-zero equation: emissions fall to a small residual at the company's
 * net-zero year, and eligible removals below the axis cancel that residual so
 * the net is zero. Hovering a step previews it, clicking pins it, clicking
 * again releases - the same state drives both the chart zones and the legend.
 */
const NetZeroChart: React.FC = () => {
  const reduceMotion = useReducedMotion();
  const [hovered, setHovered] = useState<ZoneId | null>(null);
  const [pinned, setPinned] = useState<ZoneId | null>(null);
  const active = hovered ?? pinned;
  const zoneClass = (zone: ZoneId) =>
    `cursor-pointer transition-opacity duration-300 ${active && active !== zone ? 'opacity-[0.18]' : 'opacity-100'}`;
  const keyClass = (zone: ZoneId) =>
    `text-left transition-opacity duration-300 ${active && active !== zone ? 'opacity-40' : 'opacity-100'}`;

  return (
    <div>
      <svg
        viewBox="0 0 1040 372"
        role="img"
        aria-label={NET_ZERO_CHART_LABEL}
        className="block h-auto w-full overflow-visible"
      >
        <defs>
          <linearGradient id="netzero-rose" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stopColor={KPI.reduction} stopOpacity="0.3" />
            <stop offset="1" stopColor={KPI.reduction} stopOpacity="0.08" />
          </linearGradient>
          <pattern id="netzero-hair" width="7" height="7" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="7" stroke={NEUTRAL[150]} strokeWidth="1.2" />
          </pattern>
        </defs>

        <g stroke={NEUTRAL[100]}>
          <line x1="70" y1="40" x2="980" y2="40" />
          <line x1="70" y1="102" x2="980" y2="102" />
          <line x1="70" y1="165" x2="980" y2="165" />
          <line x1="70" y1="228" x2="980" y2="228" />
        </g>
        <text x="58" y="44" textAnchor="end" fontSize="12" fill={TEXT.muted}>
          100%
        </text>
        <text x="58" y="294" textAnchor="end" fontSize="12" fill={TEXT.muted}>
          0
        </text>

        <g
          className={zoneClass('1')}
          onMouseEnter={() => setHovered('1')}
          onMouseLeave={() => setHovered(null)}
        >
          <title>Abatement: emissions you cut in your own value chain first</title>
          <path d="M70,40 C330,48 480,230 760,262 L760,40 Z" fill="url(#netzero-hair)" />
        </g>
        <g
          className={zoneClass('2')}
          onMouseEnter={() => setHovered('2')}
          onMouseLeave={() => setHovered(null)}
        >
          <title>Ongoing emissions: addressed by avoidance credits as a contribution, not net-zero</title>
          <path d="M70,40 C330,48 480,230 760,262 L760,290 L70,290 Z" fill="url(#netzero-rose)" />
        </g>

        <motion.path
          d="M70,40 C330,48 480,230 760,262 L980,262"
          fill="none"
          stroke={TEXT.primary}
          strokeWidth="2.5"
          strokeLinecap="round"
          initial={reduceMotion ? false : { pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.6, ease: [0.16, 1, 0.3, 1], delay: 0.15 }}
        />

        <g
          className={zoneClass('3')}
          onMouseEnter={() => setHovered('3')}
          onMouseLeave={() => setHovered(null)}
        >
          <title>Residual emissions: must be neutralized by eligible removals</title>
          <motion.rect
            x="760"
            y="262"
            width="220"
            height="28"
            fill={TEXT.primary}
            style={{ transformBox: 'fill-box', transformOrigin: 'bottom' }}
            initial={reduceMotion ? false : { scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 1.2 }}
          />
          <motion.g
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 1.8 }}
          >
            <text x="776" y="281" fontSize="12.5" fontWeight="600" fill={TEXT.inverse}>
              Residual emissions
            </text>
          </motion.g>
          <motion.rect
            x="760"
            y="290"
            width="220"
            height="28"
            fill={KPI.removal}
            style={{ transformBox: 'fill-box', transformOrigin: 'top' }}
            initial={reduceMotion ? false : { scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1], delay: 1.45 }}
          />
          <motion.g
            initial={reduceMotion ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.5, delay: 1.8 }}
          >
            <text x="776" y="309" fontSize="12.5" fontWeight="600" fill={TEXT.inverse}>
              Removals
            </text>
            <path
              d="M992,264 l8,0 l0,52 l-8,0"
              fill="none"
              stroke={KPI.removalDeep}
              strokeWidth="1.5"
            />
            <text x="1008" y="300" fontSize="26" fontWeight="600" fill={KPI.removalDeep} fontFamily="Poppins">
              0
            </text>
            <text x="1008" y="318" fontSize="11" fontWeight="600" fill={KPI.removalDeep}>
              net
            </text>
          </motion.g>
        </g>

        <line x1="70" y1="290" x2="980" y2="290" stroke={TEXT.primary} strokeWidth="1.25" />
        <line x1="760" y1="24" x2="760" y2="336" stroke={TEXT.primary} strokeDasharray="2 5" strokeLinecap="round" />
        <text x="70" y="358" fontSize="12.5" fill={TEXT.muted}>
          Base year
        </text>
        <text x="760" y="358" textAnchor="middle" fontSize="12.5" fontWeight="600" fill={TEXT.primary}>
          Your net-zero year
        </text>
      </svg>

      <div className="mt-6 grid grid-cols-1 border-t border-border-ui sm:mt-7 sm:grid-cols-3">
        {ZONE_IDS.map((zone, index) => {
          const key = NET_ZERO_KEYS[zone];
          return (
            <button
              key={zone}
              type="button"
              aria-pressed={pinned === zone}
              className={`min-w-0 py-4 text-left focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-inset sm:py-5 ${
                index > 0 ? 'border-t border-border-ui sm:border-t-0 sm:border-l sm:border-border-ui sm:pl-5' : 'sm:pr-5'
              } ${keyClass(zone)}`}
              onMouseEnter={() => setHovered(zone)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(zone)}
              onBlur={() => setHovered(null)}
              onClick={() => setPinned(pinned === zone ? null : zone)}
            >
              <h4 className="font-poppins text-body-sm 3xl:text-base font-semibold text-text-primary">
                {key.title}
              </h4>
              <p className="mt-1.5 text-pretty font-inter text-caption 3xl:text-ui leading-relaxed text-text-secondary">
                {key.body}
              </p>
              {key.status ? (
                <span className="mt-2.5 inline-flex items-center gap-2 font-inter text-caption font-semibold text-text-primary">
                  <span
                    aria-hidden="true"
                    className={`h-2 w-2 shrink-0 rounded-full ${STATUS_DOT[key.status.tone]}`}
                  />
                  {key.status.label}
                </span>
              ) : null}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default NetZeroChart;
