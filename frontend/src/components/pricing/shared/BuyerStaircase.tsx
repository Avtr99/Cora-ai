import React, { useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { Building2, Check, Landmark, Minus, Plane, Plus, type LucideIcon } from 'lucide-react';
import { COMPLIANCE_STAIRCASE, type StairIconId, type StairLevel, type StairPool } from '@/data/pricingFactorContent';

const POOL_ICONS: Record<StairIconId, LucideIcon> = {
  plane: Plane,
  landmark: Landmark,
  building: Building2,
};

const missing = (pool: StairPool, level: StairLevel) =>
  pool.needs.filter((requirement) => !level.met.includes(requirement));

const needText = (unmet: number[]) =>
  unmet.includes(0) ? 'Needs authorization' : 'Needs ICAO programme and 2016+ start';

/** Row 1 is the header, then one row per buyer pool, then the count row. */
const cellAt = (row: number, column: number): React.CSSProperties => ({ gridRow: row, gridColumn: column });

/**
 * Buyer-pool staircase: rows are buyer pools, columns are authorization
 * levels, and the cells that can bid form the staircase. The highlight band is
 * a grid item on the selected column, so it sits exactly in that column's
 * gutters and never bleeds into a neighbour.
 */
const BuyerStaircase: React.FC = () => {
  const { pools, levels } = COMPLIANCE_STAIRCASE;
  const reduceMotion = useReducedMotion();
  const [selected, setSelected] = useState(1);
  const level = levels[selected];
  const countRow = pools.length + 2;

  return (
    <div>
      <div
        role="table"
        aria-label="Buyer pools that can bid at each authorization level"
        className="grid grid-cols-[6rem_repeat(3,minmax(0,1fr))] gap-x-1.5 gap-y-2 sm:grid-cols-[minmax(170px,1.1fr)_repeat(3,minmax(0,1fr))] sm:gap-x-3 sm:gap-y-2.5"
      >
        <span
          aria-hidden="true"
          className="pointer-events-none -my-2.5 -mx-[3px] rounded-xl bg-surface-base shadow-[inset_0_0_0_1px_var(--color-border-ui)] transition-opacity duration-200 sm:-my-[14px] sm:-mx-1.5"
          style={{ gridRow: `1 / ${countRow + 1}`, gridColumn: selected + 2 }}
        />

        <div role="row" className="contents">
          <span
            role="columnheader"
            style={cellAt(1, 1)}
            className="relative self-end pb-3 font-inter text-overline font-semibold uppercase tracking-wider text-text-muted"
          >
            Buyer pool
          </span>
          {levels.map((column, index) => (
            <div role="columnheader" key={column.name} style={cellAt(1, index + 2)} className="relative min-w-0">
              <button
                type="button"
                aria-pressed={selected === index}
                onClick={() => setSelected(index)}
                className="flex w-full flex-col items-start justify-end gap-1.5 pb-3 text-left focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-inset"
              >
                <span
                  className={`hidden items-center gap-1 font-inter text-overline font-semibold text-text-muted sm:flex`}
                >
                  {column.gateIcon ? <Plus aria-hidden="true" strokeWidth={3} className="h-3 w-3" /> : null}
                  {column.gate}
                </span>
                <span
                  className={`font-poppins text-caption font-semibold leading-snug transition-colors duration-200 sm:text-body-sm 3xl:text-base ${
                    selected === index ? 'text-text-primary' : 'text-text-secondary'
                  }`}
                >
                  {column.name}
                </span>
              </button>
            </div>
          ))}
        </div>

        {pools.map((pool, rowIndex) => {
          const Icon = POOL_ICONS[pool.icon];
          return (
            <div role="row" key={pool.name} className="contents">
              <div
                role="rowheader"
                style={cellAt(rowIndex + 2, 1)}
                className="relative grid min-w-0 grid-cols-1 items-center gap-1 sm:grid-cols-[2.25rem_minmax(0,1fr)] sm:gap-3"
              >
                <span className="hidden h-9 w-9 place-items-center rounded-[10px] bg-surface-subtle text-text-primary sm:grid">
                  <Icon aria-hidden="true" strokeWidth={2} className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0">
                  <b className="block font-inter text-caption leading-[1.3] font-semibold text-text-primary sm:text-body-sm">
                    {pool.name}
                  </b>
                  <small className="hidden font-inter text-caption text-text-muted sm:block">{pool.sub}</small>
                </span>
              </div>
              {levels.map((column, index) => {
                const unmet = missing(pool, column);
                if (unmet.length > 0) {
                  return (
                    <div
                      role="cell"
                      key={column.name}
                      style={cellAt(rowIndex + 2, index + 2)}
                      className="relative flex min-h-12 items-center justify-center gap-2 rounded-[10px] border border-dashed border-border-strong px-1.5 font-inter text-caption leading-[1.3] text-text-muted sm:min-h-[60px] sm:justify-start sm:gap-2 sm:px-3.5"
                    >
                      <Minus aria-hidden="true" strokeWidth={3} className="h-3.5 w-3.5 shrink-0" />
                      <span className="hidden sm:inline">{needText(unmet)}</span>
                    </div>
                  );
                }
                return (
                  <motion.div
                    role="cell"
                    key={column.name}
                    style={cellAt(rowIndex + 2, index + 2)}
                    className="relative flex min-h-12 origin-bottom items-center justify-center gap-2 rounded-[10px] bg-kpi-removal-soft px-1.5 font-inter text-caption leading-[1.3] font-semibold text-semantic-success-text sm:min-h-[60px] sm:justify-start sm:gap-2 sm:px-3.5"
                    initial={reduceMotion ? false : { scaleY: 0 }}
                    animate={{ scaleY: 1 }}
                    transition={{
                      duration: 0.6,
                      ease: [0.16, 1, 0.3, 1],
                      delay: 0.15 + index * 0.15 + (pools.length - 1 - rowIndex) * 0.05,
                    }}
                  >
                    <Check aria-hidden="true" strokeWidth={3} className="h-4 w-4 shrink-0" />
                    <span className="hidden sm:inline">Can buy</span>
                  </motion.div>
                );
              })}
            </div>
          );
        })}

        <div role="row" className="contents">
          {levels.map((column, index) => {
            const count = pools.filter((pool) => missing(pool, column).length === 0).length;
            return (
              <div
                role="cell"
                key={column.name}
                style={cellAt(countRow, index + 2)}
                className="relative pt-2 text-center font-inter text-caption text-text-muted tabular-nums sm:pt-2 sm:text-left"
              >
                <b className="mr-1 font-poppins text-xl leading-none font-semibold text-text-primary">{count}</b>
                <span className="hidden sm:inline">of {pools.length} buyer pools</span>
              </div>
            );
          })}
        </div>
      </div>

      <p
        aria-live="polite"
        className="mt-7 min-h-16 border-t border-border-ui pt-4.5 font-inter text-body-sm 3xl:text-body leading-relaxed text-text-secondary"
      >
        <strong className="font-semibold text-text-primary">{level.name}.</strong> {level.sub}
      </p>
    </div>
  );
};

export default BuyerStaircase;
