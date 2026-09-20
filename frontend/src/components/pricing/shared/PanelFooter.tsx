import React from 'react';
import { RELATED_FACTORS, type PricingSource } from '@/data/pricingFactorContent';
import type { ForceId } from '@/data/pricingData';

const RelatedFactor: React.FC<{
  activeForce: ForceId;
  onSelect: (force: ForceId) => void;
}> = ({ activeForce, onSelect }) => {
  const related = RELATED_FACTORS[activeForce];
  return (
    <p className="font-inter text-ui 3xl:text-sm 4xl:text-base leading-5 text-text-muted">
      {related.text}{' '}
      <button
        type="button"
        onClick={() => onSelect(related.id)}
        className="font-semibold text-brand-700 underline decoration-brand-200 underline-offset-2 transition-colors hover:text-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
      >
        {related.label}
      </button>
    </p>
  );
};

const SourceLinks: React.FC<{ sources: PricingSource[] }> = ({ sources }) => (
  <p className="font-inter text-overline 3xl:text-xs 4xl:text-sm leading-relaxed text-text-muted">
    Source:{' '}
    {sources.map((source, index) => (
      <React.Fragment key={source.href}>
        {index > 0 && <span aria-hidden="true">, </span>}
        <a
          href={source.href}
          target="_blank"
          rel="noreferrer"
          className="underline decoration-border-ui underline-offset-2 transition-colors hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
        >
          {source.label}
        </a>
      </React.Fragment>
    ))}
  </p>
);

const PanelFooter: React.FC<{
  activeForce: ForceId;
  onSelect: (force: ForceId) => void;
  sources: PricingSource[];
}> = ({ activeForce, onSelect, sources }) => (
  <footer className="mt-10 3xl:mt-14 4xl:mt-16 flex flex-wrap items-start justify-between gap-x-8 gap-y-3 pt-2">
    <RelatedFactor activeForce={activeForce} onSelect={onSelect} />
    <SourceLinks sources={sources} />
  </footer>
);

export default PanelFooter;
