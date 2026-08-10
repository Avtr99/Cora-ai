import React, { useMemo, useState } from 'react';
import { formatCredits } from '@/lib/formatCredits';

interface IssuanceSparklineProps {
  /** Sparse { year: credits } map from _detail.issuedByYear */
  issuedByYear: Record<string, number>;
  /** Years with no issuance are rendered as gaps rather than skipped */
  hasGap?: boolean;
}

const HEIGHT = 64; // Height of chart area in px

export const IssuanceSparkline: React.FC<IssuanceSparklineProps> = ({
  issuedByYear,
}) => {
  const [hoveredBar, setHoveredBar] = useState<{ year: number; value: number } | null>(null);

  const { bars, activeBars, max, firstYear, lastYear, total, peakBar } = useMemo(() => {
    const years = Object.keys(issuedByYear).map(Number).sort((a, b) => a - b);
    if (years.length === 0) {
      return { bars: [], activeBars: [], max: 0, firstYear: 0, lastYear: 0, total: 0, peakBar: null };
    }

    const first = years[0];
    const last = years[years.length - 1];

    const allBars: { year: number; value: number }[] = [];
    const active: { year: number; value: number }[] = [];
    let sum = 0;
    let peak = { year: first, value: 0 };

    for (let y = first; y <= last; y++) {
      const value = issuedByYear[String(y)] ?? 0;
      allBars.push({ year: y, value });
      if (value > 0) {
        active.push({ year: y, value });
        sum += value;
        if (value > peak.value) {
          peak = { year: y, value };
        }
      }
    }

    const peakVal = Math.max(...allBars.map((b) => b.value));

    return {
      bars: allBars,
      activeBars: active,
      max: peakVal,
      firstYear: first,
      lastYear: last,
      total: sum,
      peakBar: peak,
    };
  }, [issuedByYear]);

  if (bars.length === 0 || total === 0) return null;

  // Case 1: Single issuance year — render a clean metric badge instead of a chart
  if (activeBars.length === 1) {
    const single = activeBars[0];
    return (
      <div className="mb-5 p-3 rounded-xl bg-surface-subtle border border-border-ui/60 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-semantic-success-icon" />
          <span className="font-inter text-xs text-text-secondary font-medium">
            Single issuance in {single.year}
          </span>
        </div>
        <span className="font-inter text-xs font-semibold text-text-primary">
          {formatCredits(single.value)} credits
        </span>
      </div>
    );
  }

  // Case 2: Multi-year issuance timeline
  return (
    <div className="mb-5">
      {/* Header with dynamic readout */}
      <div className="flex items-baseline justify-between mb-2">
        <span className="font-inter text-2xs font-semibold text-text-muted uppercase tracking-[0.5px]">
          Issuance by year
        </span>
        <span className="font-inter text-xs transition-colors font-medium">
          {hoveredBar ? (
            <span className={hoveredBar.value > 0 ? 'text-semantic-success-button font-semibold' : 'text-text-muted'}>
              {hoveredBar.year}: {hoveredBar.value > 0 ? `${formatCredits(hoveredBar.value)} credits` : 'No issuance'}
            </span>
          ) : peakBar && peakBar.value > 0 ? (
            <span className="text-text-muted">
              Peak: <strong className="text-text-secondary font-medium">{peakBar.year}</strong> ({formatCredits(peakBar.value)})
            </span>
          ) : null}
        </span>
      </div>

      {/* Chart container */}
      <div
        className="flex items-end gap-[3px] pt-2 pb-1 border-b border-border-ui/40"
        style={{ height: HEIGHT }}
        role="img"
        aria-label={`Credits issued per year from ${firstYear} to ${lastYear}, ${formatCredits(total)} total.`}
        onMouseLeave={() => setHoveredBar(null)}
      >
        {bars.map(({ year, value }) => {
          const isPositive = value > 0;
          const barHeight = isPositive && max > 0 ? Math.max(6, (value / max) * (HEIGHT - 12)) : 2;
          const isHovered = hoveredBar?.year === year;

          return (
            <div
              key={year}
              onMouseEnter={() => setHoveredBar({ year, value })}
              className="flex-1 flex flex-col justify-end h-full group relative cursor-pointer"
            >
              <div
                className={`w-full rounded-t-xs transition-all duration-150 ${
                  isPositive
                    ? isHovered
                      ? 'bg-semantic-success-button ring-2 ring-semantic-success-icon/30'
                      : 'bg-semantic-success-icon hover:bg-semantic-success-button'
                    : isHovered
                    ? 'bg-border-ui ring-2 ring-border-ui/50'
                    : 'bg-border-ui/50 hover:bg-border-ui'
                }`}
                style={{ height: barHeight }}
              />
            </div>
          );
        })}
      </div>

      {/* X-axis year ticks */}
      <div className="flex justify-between mt-1.5 font-inter text-2xs text-text-muted">
        <span>{firstYear}</span>
        {peakBar && peakBar.year !== firstYear && peakBar.year !== lastYear && (
          <span className="text-text-muted/70">peak ({peakBar.year})</span>
        )}
        <span>{lastYear}</span>
      </div>
    </div>
  );
};
