import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { getProjectTypeColor, CHOROPLETH_COLORS } from '@/lib/colors';
import type { CountryAggregate } from '@/lib/mapAggregation';

interface MapLegendProps {
  aggregates: CountryAggregate[];
  totalProjects?: number;
}

interface ScopeBucket {
  scope: string;
  color: string;
  count: number;
}

function useGlobalScopes(aggregates: CountryAggregate[]): ScopeBucket[] {
  return useMemo(() => {
    const m = new Map<string, ScopeBucket>();
    for (const agg of aggregates) {
      for (const s of agg.scopes) {
        const existing = m.get(s.scope);
        if (existing) existing.count += s.count;
        else {
          m.set(s.scope, {
            scope: s.scope,
            color: getProjectTypeColor(s.scope).accent,
            count: s.count,
          });
        }
      }
    }
    return Array.from(m.values()).sort((a, b) => b.count - a.count);
  }, [aggregates]);
}

/**
 * Compact, collapsible legend pinned to the top-left of the map. Shows a
 * small summary pill by default (totals only) so it never obscures the
 * choropleth; expands on click to reveal scope colours and the choropleth
 * density scale.
 */
export const MapLegend: React.FC<MapLegendProps> = ({ aggregates, totalProjects: totalProjectsProp }) => {
  const scopes = useGlobalScopes(aggregates);
  const [open, setOpen] = useState(false);

  const totalCountries = aggregates.length;
  const totalAggregated = aggregates.reduce((n, a) => n + a.projectCount, 0);
  const unmappedCount = totalProjectsProp != null ? Math.max(0, totalProjectsProp - totalAggregated) : 0;
  const legendTotal = totalProjectsProp ?? totalAggregated;

  return (
    <div className="absolute top-3 left-3 z-20 pointer-events-none">
      <motion.div
        initial={{ opacity: 0, x: -6 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.22, ease: 'easeOut', delay: 0.08 }}
        onClick={(e) => e.stopPropagation()}
        className="pointer-events-auto"
      >
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-controls="map-legend-body"
          className="flex items-center gap-2 h-7 pl-2 pr-2.5 rounded-full bg-surface-card/90 backdrop-blur-sm border border-border-ui shadow-xs hover:shadow-card-sm transition-shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
        >
          <span
            className="w-1.5 h-1.5 rounded-full bg-brand-500"
            aria-hidden="true"
          />
          <span className="font-poppins font-semibold text-[11.5px] text-text-primary tabular-nums">
            {legendTotal.toLocaleString()}
          </span>
          <span className="font-inter text-[10.5px] text-text-muted">projects</span>
          <span className="w-px h-3 bg-border-ui mx-0.5" aria-hidden="true" />
          <span className="font-inter text-[10.5px] text-text-muted tabular-nums">
            {totalCountries.toLocaleString()} countries
          </span>
          <motion.svg
            animate={{ rotate: open ? 180 : 0 }}
            transition={{ duration: 0.18 }}
            className="w-2.5 h-2.5 text-text-muted ml-0.5"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M6 9l6 6 6-6" />
          </motion.svg>
        </button>

        <AnimatePresence initial={false}>
          {open && (
            <motion.div
              id="map-legend-body"
              initial={{ opacity: 0, y: -4, height: 0 }}
              animate={{ opacity: 1, y: 0, height: 'auto' }}
              exit={{ opacity: 0, y: -4, height: 0 }}
              transition={{ duration: 0.2, ease: 'easeOut' }}
              className="mt-1.5 w-[220px] overflow-hidden bg-surface-card/95 backdrop-blur-sm border border-border-ui rounded-xl shadow-card-sm"
            >
              <div className="px-3 py-2">
                <div className="font-poppins text-xs font-semibold text-text-muted uppercase tracking-widest mb-1.5">
                  Projects by scope
                </div>
                <div className="flex flex-col gap-0.5">
                  {scopes.map((s) => (
                    <div key={s.scope} className="flex items-center gap-2">
                      <span
                        className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: s.color }}
                      />
                      <span className="font-inter text-[10.5px] text-text-primary leading-tight flex-1 truncate">
                        {s.scope}
                      </span>
                      <span className="font-inter text-2xs text-text-muted tabular-nums flex-shrink-0">
                        {s.count.toLocaleString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {unmappedCount > 0 && (
                <div className="px-3 py-1.5 border-t border-surface-subtle">
                  <div className="flex items-start gap-1.5">
                    <svg className="w-3 h-3 text-text-muted flex-shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <circle cx="12" cy="12" r="10"/>
                      <path d="M12 16v-4M12 8h.01"/>
                    </svg>
                    <span className="font-inter text-2xs text-text-muted leading-snug">
                      {unmappedCount.toLocaleString()} project{unmappedCount === 1 ? '' : 's'} not shown - no specific country assigned.
                    </span>
                  </div>
                </div>
              )}

              <div className="px-3 py-2 border-t border-surface-subtle">
                <div className="font-poppins text-xs font-semibold text-text-muted uppercase tracking-widest mb-1.5">
                  Density (projects per country)
                </div>
                <div className="flex h-2 rounded-full overflow-hidden border border-border-ui">
                  {[...CHOROPLETH_COLORS].reverse().map((c) => (
                    <DensitySwatch key={c.color} hex={c.color} />
                  ))}
                </div>
                <div className="flex justify-between mt-1 font-inter text-[9.5px] text-text-muted tabular-nums">
                  <span>1</span>
                  <span>10</span>
                  <span>100</span>
                  <span>500+</span>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  );
};

const DensitySwatch: React.FC<{ hex: string }> = ({ hex }) => (
  <span className="flex-1" style={{ backgroundColor: hex }} />
);
