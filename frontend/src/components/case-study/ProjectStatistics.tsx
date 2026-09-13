import React, { useId } from 'react';
import { CHIP, GAUGE } from '@/lib/colors';

/** Parse a formatted number string (e.g. '211,636') into a number */
function parseFormattedNumber(value: string): number {
  return Number(value.replace(/,/g, '')) || 0;
}

interface ProjectStatisticsProps {
  carbonSequestered: string;
  permanenceRisk: {
    percentage: number;
    label: string;
  };
  bufferPool?: string;
  creditsIssued?: string;
  creditsRetired?: string;
  source?: string;
}

/**
 * SVG Semi-circle gauge chart component
 * Displays credits retired vs remaining as a donut-style gauge
 * Uses flexbox layout instead of absolute positioning for better responsiveness
 */
const CreditChart = ({ 
  retiredPercent, 
  remainingPercent,
  source 
}: { retiredPercent: number; remainingPercent: number; source: string }) => {
  const chartTitleId = useId();
  const chartDescId = `${chartTitleId}-desc`;

  // Configuration for the chart — larger viewBox allows bigger scaled arc
  const radius = 140;
  const stroke = 32;
  const width = 360;
  const height = 210;
  const center = { x: width / 2, y: height - 18 };

  // Colors
  const colors = {
    purple: GAUGE.retired,
    green: GAUGE.remaining,
  };

  // Helper: Convert degrees to Cartesian coordinates
  const polarToCartesian = (centerX: number, centerY: number, r: number, angleInDegrees: number) => {
    const angleInRadians = ((angleInDegrees - 180) * Math.PI) / 180.0;
    return {
      x: centerX + r * Math.cos(angleInRadians),
      y: centerY + r * Math.sin(angleInRadians),
    };
  };

  // Helper: Create the SVG Path string
  const describeArc = (x: number, y: number, r: number, startAngle: number, endAngle: number) => {
    const start = polarToCartesian(x, y, r, endAngle);
    const end = polarToCartesian(x, y, r, startAngle);
    const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';
    return ['M', start.x, start.y, 'A', r, r, 0, largeArcFlag, 0, end.x, end.y].join(' ');
  };

  // Calculate Angles (Total 180 degrees)
  const gapSize = 3;
  const totalArc = 180;
  const splitAngle = (retiredPercent / 100) * totalArc;
  
  // Path Definitions
  const purplePath = describeArc(center.x, center.y, radius, 0, splitAngle - gapSize / 2);
  const greenPath = describeArc(center.x, center.y, radius, splitAngle + gapSize / 2, totalArc);

  // Arc tip positions as percentages of viewBox width for responsive alignment
  const leftTipPct = ((center.x - radius) / width) * 100;
  const rightTipPct = ((center.x + radius) / width) * 100;

  return (
    <div className="flex flex-col w-full lg:w-[460px] 3xl:w-[560px] 4xl:w-[680px]">
      <div className="w-full max-w-full sm:max-w-[340px] lg:max-w-[420px] 3xl:max-w-[520px] 4xl:max-w-[620px] mx-auto lg:mx-0 relative">
        {/* Labels positioned above chart at arc tip locations */}
        <div className="absolute top-0 left-0 right-0 z-10">
          {/* Left Label - Credits retired */}
          <div className="absolute top-0 flex flex-col items-center" style={{ left: `${leftTipPct}%`, transform: 'translateX(-50%)' }}>
            <div className="text-gauge-retired text-base sm:text-lg lg:text-2xl 3xl:text-3xl 4xl:text-4xl font-poppins font-semibold leading-[24px] lg:leading-[28px] 3xl:leading-[34px] 4xl:leading-[40px]">{retiredPercent}%</div>
            <div title="Credits retired" className="text-text-muted text-2xs sm:text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-medium leading-[16px] 3xl:leading-[20px] max-w-[80px] 3xl:max-w-[160px] text-center truncate">Credits retired</div>
          </div>

          {/* Right Label - Credits remaining */}
          <div className="absolute top-0 flex flex-col items-center" style={{ left: `${rightTipPct}%`, transform: 'translateX(-50%)' }}>
            <div className="text-semantic-success-text text-base sm:text-lg lg:text-2xl 3xl:text-3xl 4xl:text-4xl font-poppins font-semibold leading-[24px] lg:leading-[28px] 3xl:leading-[34px] 4xl:leading-[40px]">{remainingPercent}%</div>
            <div title="Credits remaining" className="text-text-muted text-2xs sm:text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-medium leading-[16px] 3xl:leading-[20px] max-w-[80px] 3xl:max-w-[160px] text-center truncate">Credits remaining</div>
          </div>
        </div>

        {/* SVG Gauge — tight gap from labels */}
        <div className="w-full h-[140px] sm:h-[160px] lg:h-[190px] 3xl:h-[230px] 4xl:h-[280px] pt-6 sm:pt-7 lg:pt-8 3xl:pt-10 4xl:pt-12">
          <svg
            role="img"
            aria-labelledby={`${chartTitleId} ${chartDescId}`}
            focusable="false"
            width="100%"
            height="100%"
            viewBox={`0 0 ${width} ${height}`}
            preserveAspectRatio="xMidYMax meet"
            className="block"
          >
            <title id={chartTitleId}>Carbon credit retirement vs remaining gauge</title>
            <desc id={chartDescId}>
              {retiredPercent}% of credits retired compared to {remainingPercent}% remaining.
            </desc>
            <path d={purplePath} fill="none" stroke={colors.purple} strokeWidth={stroke} strokeLinecap="butt" />
            <path d={greenPath} fill="none" stroke={colors.green} strokeWidth={stroke} strokeLinecap="butt" />
          </svg>
        </div>

        {/* Source text */}
        <div className="text-text-muted text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-medium leading-[16px] 3xl:leading-[20px] text-center lg:text-right mt-1 lg:mt-2 3xl:mt-3">
          Source: {source}
        </div>
      </div>
    </div>
  );
};

/**
 * Component to display project statistics with a gauge chart
 * Matches the Figma design with proper styling and layout
 */
export const ProjectStatistics = ({
  carbonSequestered,
  permanenceRisk,
  bufferPool = '32,882',
  creditsIssued = '211,636',
  creditsRetired = '167,291',
  source = 'VCS',
}: ProjectStatisticsProps) => {
  const labelId = useId();

  // Compute actual retired percentage from credits data
  const issued = parseFormattedNumber(creditsIssued);
  const retired = parseFormattedNumber(creditsRetired);
  const rawRetiredPercent = issued > 0 ? Math.round((retired / issued) * 100) : 0;
  const retiredPercent = Math.min(Math.max(rawRetiredPercent, 0), 100);
  const remainingPercent = 100 - retiredPercent;
  
  return (
    <div className="mb-6 md:mb-16 3xl:mb-20 4xl:mb-24">
      <div className="bg-surface-card rounded-2xl p-4 md:p-7 3xl:p-9 4xl:p-12 shadow-sm border border-border-ui mb-6 md:mb-12 3xl:mb-14 4xl:mb-16">
        <div className="flex flex-col md:flex-row justify-between items-start gap-3 md:gap-8 3xl:gap-10 4xl:gap-12">
          {/* Left side - Stats */}
          <div className="w-full md:w-auto flex flex-col gap-5 md:gap-8 3xl:gap-10 4xl:gap-12">
            {/* Issuances Remaining - Header */}
            <div className="flex flex-col gap-1 md:gap-1.5 3xl:gap-2">
              <p id={labelId} className="text-xs 3xl:text-[15px] 4xl:text-lg uppercase text-text-muted font-inter font-semibold leading-[14px] 3xl:leading-[18px] tracking-wide">ISSUANCES REMAINING</p>
              <div aria-labelledby={labelId} className="text-text-primary text-2xl md:text-3xl 3xl:text-4xl 4xl:text-5xl font-inter font-semibold leading-[24px] md:leading-[36px] 3xl:leading-[44px] 4xl:leading-[56px]">{carbonSequestered}</div>
            </div>
            
            {/* Chips - wrapped together in a row */}
            <div className="flex flex-wrap gap-3 md:gap-5 3xl:gap-6 4xl:gap-8">
              <div className="flex flex-col gap-0.5 3xl:gap-1">
                <span className="text-text-muted text-xs md:text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-medium">Buffer Pool</span>
                <div className="flex items-center justify-center py-1 3xl:py-1.5 4xl:py-2 px-2.5 3xl:px-3.5 rounded-lg" style={{ backgroundColor: CHIP.positive.bg }}>
                  <span className="font-inter font-semibold text-xs md:text-xs 3xl:text-[15px] 4xl:text-lg text-text-primary">{bufferPool}</span>
                </div>
              </div>
              <div className="flex flex-col gap-0.5 3xl:gap-1">
                <span className="text-text-muted text-xs md:text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-medium">Credits issued</span>
                <div className="flex items-center justify-center py-1 3xl:py-1.5 4xl:py-2 px-2.5 3xl:px-3.5 rounded-lg" style={{ backgroundColor: CHIP.neutral.bg }}>
                  <span className="font-inter font-semibold text-xs md:text-xs 3xl:text-[15px] 4xl:text-lg text-text-primary">{creditsIssued}</span>
                </div>
              </div>
              <div className="flex flex-col gap-0.5 3xl:gap-1">
                <span className="text-text-muted text-xs md:text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-medium">Credits retired</span>
                <div className="flex items-center justify-center py-1 3xl:py-1.5 4xl:py-2 px-2.5 3xl:px-3.5 rounded-lg" style={{ backgroundColor: CHIP.info.bg }}>
                  <span className="font-inter font-semibold text-xs md:text-xs 3xl:text-[15px] 4xl:text-lg text-text-primary">{creditsRetired}</span>
                </div>
              </div>
            </div>
          </div>
          
          {/* Right side - Credit Chart */}
          <div className="w-full md:w-auto flex justify-center md:justify-end mt-6 md:mt-0">
            <CreditChart retiredPercent={retiredPercent} remainingPercent={remainingPercent} source={source} />
          </div>
        </div>
      </div>
    </div>
  );
};
