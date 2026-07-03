import React from 'react';
import { motion } from 'framer-motion';
import type { VCMProject } from '@/types/project';
import type { CountryAggregate } from '@/lib/mapAggregation';
import { formatCredits } from '@/lib/formatCredits';

interface MapCountryTooltipProps {
  agg: CountryAggregate;
  onProjectClick: (p: VCMProject) => void;
  onEnter?: () => void;
  onLeave?: () => void;
}

const TOOLTIP_WIDTH = 260;

/**
 * Docked hover card. Pinned to the bottom-left of the map container so the
 * card never occludes the country being hovered — critical for small
 * countries where a cursor-following tooltip would sit directly on top of
 * the polygon. The user always knows where to look.
 */
export const MapCountryTooltip: React.FC<MapCountryTooltipProps> = ({
  agg,
  onProjectClick,
  onEnter,
  onLeave,
}) => {
  const scopeTotal = agg.scopes.reduce((n, s) => n + s.count, 0) || 1;
  const pctRetired = agg.creditsIssued > 0
    ? Math.round((agg.creditsRetired / agg.creditsIssued) * 100)
    : 0;

  return (
    <motion.div
      key={agg.country}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8 }}
      transition={{ duration: 0.16, ease: [0.22, 1, 0.36, 1] }}
      className="absolute bottom-4 left-4 z-30"
      style={{ width: TOOLTIP_WIDTH }}
      onMouseEnter={onEnter}
      onMouseLeave={onLeave}
      onClick={(e) => e.stopPropagation()}
      role="dialog"
      aria-label={`Details for ${agg.country}`}
    >
      <div className="bg-surface-card/95 backdrop-blur-sm rounded-xl border border-border-ui shadow-card overflow-hidden ring-1 ring-black/[0.02]">
        {/* Country + totals */}
        <div className="px-3 pt-2.5 pb-2 border-b border-surface-subtle">
          <div className="flex items-baseline justify-between">
            <h4 className="font-poppins font-semibold text-sm text-text-primary leading-tight truncate">
              {agg.country}
            </h4>
            <span className="font-poppins font-semibold text-sm text-text-primary tabular-nums">
              {agg.projectCount}
            </span>
          </div>
          <div className="flex items-center gap-2 mt-1">
            <span className="font-inter text-2xs text-text-muted">
              {formatCredits(agg.creditsIssued)} credits
            </span>
            {agg.creditsIssued > 0 && (
              <>
                <span className="w-px h-2 bg-border-ui" />
                <span className="font-inter text-2xs text-text-muted">
                  {pctRetired}% retired
                </span>
              </>
            )}
          </div>
        </div>

        {/* Scope mini-bar */}
        {agg.scopes.length > 0 && (
          <div className="px-3 py-2 border-b border-surface-subtle">
            <div className="flex h-1 w-full rounded-full overflow-hidden bg-surface-subtle mb-1.5">
              {agg.scopes.map((s) => (
                <div
                  key={s.scope}
                  className="h-full"
                  style={{
                    width: `${(s.count / scopeTotal) * 100}%`,
                    backgroundColor: s.color,
                  }}
                />
              ))}
            </div>
            <div className="flex flex-col gap-0.5">
              {agg.scopes.slice(0, 3).map((s) => (
                <div key={s.scope} className="flex items-center gap-1.5">
                  <span
                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: s.color }}
                  />
                  <span className="font-inter text-[10.5px] text-text-secondary flex-1 truncate">
                    {s.scope}
                  </span>
                  <span className="font-inter text-2xs text-text-muted tabular-nums">
                    {s.count}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Top projects */}
        <div className="px-2.5 py-1.5">
          <div className="font-poppins text-xs font-semibold text-text-muted uppercase tracking-widest px-1 pt-1 pb-1">
            Top projects
          </div>
          <ul className="flex flex-col">
            {agg.topProjects.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  onClick={() => onProjectClick(p)}
                  aria-label={`Open project ${p.name} — ${formatCredits(p.creditsIssued)}, ${p.type}`}
                  className="w-full text-left px-2 py-1.5 rounded-md hover:bg-surface-base transition-colors focus:outline-none focus-visible:bg-brand-100"
                >
                  <div className="font-inter text-xs text-text-primary font-medium leading-tight line-clamp-1">
                    {p.name}
                  </div>
                  <div className="flex items-center gap-1.5 mt-0.5">
                    <span className="font-inter text-[9.5px] text-text-muted tabular-nums">
                      {formatCredits(p.creditsIssued)}
                    </span>
                    <span className="w-0.5 h-0.5 rounded-full bg-border-ui" />
                    <span className="font-inter text-[9.5px] text-text-muted truncate">
                      {p.type}
                    </span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
          <div className="px-2 pt-1 pb-1.5 font-inter text-2xs text-brand-700">
            Click a project to view details →
          </div>
        </div>
      </div>
    </motion.div>
  );
};
