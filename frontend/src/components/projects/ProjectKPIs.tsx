import React, { useMemo } from 'react';
import type { VCMProject } from '@/types/project';
import { formatCredits } from '@/lib/formatCredits';
import { isMetaCountry } from '@/lib/countryCoordinates';
import { KPI } from '@/lib/colors';

interface ProjectKPIsProps {
  projects: VCMProject[];
  filteredCount: number;
}

// Methodology split — semantic data colors from the design system
const RR_COLORS: Record<string, string> = {
  Reduction: KPI.reduction,
  Removal: KPI.removal,
  Other: KPI.other,
};

/**
 * Returns a human-readable label for a registry code.
 * Known registries map to short names; unknown ones get title-cased.
 */
function getRegistryLabel(code: string): string {
  const known: Record<string, string> = {
    VCS: 'VCS',
    GOLD: 'GS',
    CAR: 'CAR',
    ACR: 'ACR',
    ART: 'ART',
    ISO: 'ISO',
  };
  return known[code.toUpperCase()] || code.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

export const ProjectKPIs: React.FC<ProjectKPIsProps> = ({ projects, filteredCount }) => {
  const stats = useMemo(() => {
    let totalIssued = 0;
    const registryMap = new Map<string, number>();
    const rrMap = new Map<string, number>();
    const countryMap = new Map<string, number>();

    let totalRetired = 0;
    for (const p of projects) {
      totalIssued += p.creditsIssued;
      totalRetired += p.creditsRetired;
      registryMap.set(p.registry, (registryMap.get(p.registry) || 0) + 1);
      const rrKey = p.reductionRemoval || 'Other';
      rrMap.set(rrKey, (rrMap.get(rrKey) || 0) + 1);
      if (p.country && !isMetaCountry(p.country)) countryMap.set(p.country, (countryMap.get(p.country) || 0) + 1);
    }

    const registryData = Array.from(registryMap.entries())
      .filter(([name]) => name && name.trim() !== '')
      .sort((a, b) => b[1] - a[1])
      .map(([name, value]) => ({ name, value }));

    const rrBuckets = { Reduction: 0, Removal: 0, Other: 0 };
    for (const [key, count] of rrMap.entries()) {
      const lower = key.toLowerCase();
      if (lower.includes('reduction')) rrBuckets.Reduction += count;
      else if (lower.includes('removal')) rrBuckets.Removal += count;
      else rrBuckets.Other += count;
    }
    const rrData = Object.entries(rrBuckets)
      .filter(([, v]) => v > 0)
      .map(([name, value]) => ({ name, value }));

    const rrTotal = rrData.reduce((sum, d) => sum + d.value, 0);
    const countryCount = countryMap.size;

    const retiredPct = totalIssued > 0 ? Math.round((totalRetired / totalIssued) * 100) : 0;

    return { totalIssued, totalRetired, retiredPct, registryData, rrData, rrTotal, countryCount };
  }, [projects]);

  const isFiltered = filteredCount !== projects.length;
  const registryTotal = projects.length;

  const cardClass = 'bg-surface-card rounded-xl border border-border-ui px-5 py-4 shadow-xs flex flex-col justify-between';

  return (
    <div className="mb-8 mt-2 max-w-7xl mx-auto w-full">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
        
        {/* Card 1: Projects */}
        <div className={cardClass}>
          <h2 className="font-poppins text-2xs font-semibold text-text-muted uppercase tracking-widest">Projects</h2>
          <div className="flex flex-col pt-3">
            <div className="flex items-baseline gap-1.5">
              <span className="font-poppins font-semibold text-[1.6rem] leading-none text-text-primary tracking-tight tabular-nums">
                {filteredCount.toLocaleString()}
              </span>
              {isFiltered && (
                <span className="font-inter text-xs text-text-muted">
                  / {projects.length.toLocaleString()}
                </span>
              )}
            </div>
            <p className="font-inter text-xs text-text-muted mt-2 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-semantic-success-icon"></span>
              <span>{stats.countryCount} countries represented</span>
            </p>
          </div>
        </div>

        {/* Card 2: Volume */}
        <div className={cardClass}>
          <h2 className="font-poppins text-2xs font-semibold text-text-muted uppercase tracking-widest">Volume Issued</h2>
          <div className="flex flex-col pt-3">
            <span className="font-poppins font-semibold text-[1.6rem] leading-none text-text-primary tracking-tight tabular-nums">
              {formatCredits(stats.totalIssued)}
            </span>
            <p className="font-inter text-xs text-text-muted mt-2 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-semantic-success-icon"></span>
              <span>{stats.retiredPct}% credits retired</span>
            </p>
          </div>
        </div>

        {/* Card 3: Quality Standards */}
        <div className={cardClass}>
          <h2 className="font-poppins text-2xs font-semibold text-text-muted uppercase tracking-widest">Quality Standards</h2>
          <div className="flex flex-col gap-[5px] pt-3">
            {stats.registryData.map((r) => {
              const rawPct = registryTotal > 0 ? (r.value / registryTotal) * 100 : 0;
              const pct = rawPct < 1 ? parseFloat(rawPct.toFixed(1)) : Math.round(rawPct);
              const label = getRegistryLabel(r.name);
              return (
                <div key={r.name} className="flex items-center">
                  <span className="font-poppins text-xs font-medium text-text-secondary tracking-wide flex-1 min-w-0 truncate">
                    {label}
                  </span>
                  <span className="font-poppins font-semibold text-xs text-text-primary tabular-nums w-[32px] text-right flex-shrink-0">
                    {pct}%
                  </span>
                  <span className="font-inter text-2xs text-text-muted tabular-nums w-[40px] text-right flex-shrink-0">
                    {r.value.toLocaleString()}
                  </span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Card 4: Methodology Split */}
        <div className={cardClass}>
          <h2 className="font-poppins text-2xs font-semibold text-text-muted uppercase tracking-widest">Methodology Split</h2>
          <div className="flex flex-col pt-3">
            {stats.rrTotal > 0 ? (
              <>
                <div className="flex flex-col gap-[5px]">
                  {stats.rrData.map((r) => (
                    <div key={r.name} className="flex items-center justify-between">
                      <div className="flex items-center gap-1.5">
                        <span className="w-[6px] h-[6px] rounded-sm" style={{ backgroundColor: RR_COLORS[r.name] || RR_COLORS.Other }}></span>
                        <span className="font-poppins text-xs font-medium text-text-secondary tracking-wide">{r.name}</span>
                      </div>
                      <span className="font-poppins font-semibold text-xs text-text-primary tabular-nums">
                        {Math.round((r.value / stats.rrTotal) * 100)}%
                      </span>
                    </div>
                  ))}
                </div>
                
                <div className="w-full h-[5px] rounded-full overflow-hidden flex bg-surface-subtle mt-3">
                  {stats.rrData.map((r) => (
                    <div
                      key={r.name}
                      className="h-full transition-all duration-700 ease-in-out border-r border-surface-card/20 last:border-0"
                      style={{
                        width: `${(r.value / stats.rrTotal) * 100}%`,
                        backgroundColor: RR_COLORS[r.name] || RR_COLORS.Other,
                      }}
                    />
                  ))}
                </div>
              </>
            ) : (
                <div className="text-xs font-inter text-text-muted pb-1">No methodology data available.</div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
