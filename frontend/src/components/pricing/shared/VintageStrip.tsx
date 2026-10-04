import React from 'react';
import { TONE_COLORS } from '@/components/pricing/shared/barItems';
import { VINTAGE_STRIP } from '@/data/pricingFactorContent';

/**
 * Vintage years in one strip, split at the five-year cutoff: each group
 * carries its 2024 average price above the years it covers, in the same
 * colors as the price bars, so the strip reads as the same data.
 */
const VintageStrip: React.FC = () => {
  const { years, cutoff, older, recent, bought, ariaLabel } = VINTAGE_STRIP;

  return (
    <div role="img" aria-label={ariaLabel} className="grid grid-cols-9 gap-1">
      <div
        className="col-start-1 col-span-4 row-start-1 mb-1.5 border-b-2 pb-2.5"
        style={{ borderColor: TONE_COLORS.neutral }}
      >
        <small className="block font-inter text-caption text-text-muted">{older.label}</small>
        <b className="mt-0.5 block font-poppins text-body 3xl:text-xl font-semibold tracking-tight text-text-primary tabular-nums">
          {older.display}
        </b>
      </div>
      <div
        className="col-start-5 col-span-5 row-start-1 mb-1.5 border-b-2 pb-2.5"
        style={{ borderColor: TONE_COLORS.removal }}
      >
        <small className="block font-inter text-caption text-text-muted">{recent.label}</small>
        <b className="mt-0.5 block font-poppins text-body 3xl:text-xl font-semibold tracking-tight text-semantic-success-text tabular-nums">
          {recent.display}
        </b>
      </div>
      {years.map((year) => (
        <span
          key={year}
          className={`row-start-2 grid h-10 place-items-center rounded-md font-inter text-caption tabular-nums ${
            year >= cutoff ? 'bg-kpi-removal font-semibold text-text-inverse' : 'bg-surface-subtle text-text-muted'
          }`}
        >
          {year}
        </span>
      ))}
      <span className="col-start-6 col-span-4 row-start-3 mt-1 justify-self-end font-inter text-caption font-semibold text-text-primary">
        {bought}
      </span>
    </div>
  );
};

export default VintageStrip;
