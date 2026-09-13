import React, { useEffect, useRef } from 'react';
import { FORCE_ORDER, FORCES, type ForceId } from '@/data/pricingData';

interface PricingFactorTabsProps {
  activeForce: ForceId;
  onChange: (force: ForceId) => void;
}

/**
 * One tablist, two geometries: below md the buttons are FilterPanel-style
 * underline tabs in a horizontally scrolling row under a bottom rule (the
 * clipped next label is the scroll cue); at md and up they become the divided
 * five-cell strip with subtitles.
 */
const PricingFactorTabs: React.FC<PricingFactorTabsProps> = ({ activeForce, onChange }) => {
  const buttonRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Keep the active tab visible inside the scrollable strip - deep links and
  // related-factor jumps change the selection without a pointer/focus event,
  // which is what normally scrolls a tab into view.
  useEffect(() => {
    const container = scrollRef.current;
    const active = buttonRefs.current[FORCE_ORDER.indexOf(activeForce)];
    if (!container || !active) return;
    const target = active.offsetLeft - (container.clientWidth - active.offsetWidth) / 2;
    container.scrollLeft = Math.max(0, target);
  }, [activeForce]);

  const selectAt = (index: number) => {
    const normalizedIndex = (index + FORCE_ORDER.length) % FORCE_ORDER.length;
    onChange(FORCE_ORDER[normalizedIndex]);
    buttonRefs.current[normalizedIndex]?.focus();
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, index: number) => {
    if (event.key === 'ArrowRight') {
      event.preventDefault();
      selectAt(index + 1);
    } else if (event.key === 'ArrowLeft') {
      event.preventDefault();
      selectAt(index - 1);
    } else if (event.key === 'Home') {
      event.preventDefault();
      selectAt(0);
    } else if (event.key === 'End') {
      event.preventDefault();
      selectAt(FORCE_ORDER.length - 1);
    }
  };

  return (
    <div ref={scrollRef} className="relative overflow-x-auto border-b border-surface-subtle md:rounded-xl md:border md:border-border-ui md:bg-surface-base">
      <div className="flex items-center md:grid md:min-w-[58rem] md:grid-cols-5 3xl:min-w-[72rem] 4xl:min-w-[84rem]" role="tablist" aria-label="Price factors">
        {FORCE_ORDER.map((id, index) => {
          const force = FORCES[id];
          const isActive = id === activeForce;
          return (
            <button
              key={id}
              ref={(element) => {
                buttonRefs.current[index] = element;
              }}
              id={`pricing-tab-${id}`}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls="pricing-panel"
              tabIndex={isActive ? 0 : -1}
              onClick={() => onChange(id)}
              onKeyDown={(event) => handleKeyDown(event, index)}
              className={`relative inline-flex min-h-touch shrink-0 items-center whitespace-nowrap px-3 py-2.5 text-left font-inter transition-colors duration-200 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-inset active:bg-surface-muted motion-reduce:transition-none md:min-h-[88px] md:flex-col md:items-start md:justify-center md:gap-1.5 md:border-r md:border-border-ui md:px-5 md:py-4 md:last:border-r-0 3xl:min-h-[104px] 3xl:gap-2 3xl:px-6 3xl:py-5 4xl:min-h-[120px] 4xl:gap-2.5 4xl:px-7 4xl:py-6 ${
                isActive
                  ? 'text-text-primary md:bg-surface-card md:shadow-xs'
                  : 'text-text-muted hover:text-text-primary md:text-text-secondary md:hover:bg-surface-subtle'
              }`}
            >
              <span className={`whitespace-nowrap text-body-sm 3xl:text-sm 4xl:text-base ${isActive ? 'font-semibold' : 'font-medium'}`}>{force.label}</span>
              <span aria-hidden="true" className="hidden text-caption 3xl:text-xs 4xl:text-sm text-text-muted md:block">
                {force.subtitle}
              </span>
              {isActive && (
                <span aria-hidden="true" className="absolute bottom-0 left-3 right-3 h-[2px] rounded-t bg-brand-900 md:hidden" />
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
};

export default PricingFactorTabs;
