import React, { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ScrollToTop } from '../components/ui/ScrollToTop';
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChevronLeftIcon from '@/assets/icons/chevron-left.svg?react';
import PricingFactorTabs from '@/components/pricing/PricingFactorTabs';
import PricingExplorer from '@/components/pricing/PricingExplorer';
import { FORCE_ORDER, type ForceId } from '@/data/pricingData';

const parseFactorParam = (value: string | null): ForceId =>
  FORCE_ORDER.includes(value as ForceId) ? (value as ForceId) : 'type';

const PricingPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeForce = parseFactorParam(searchParams.get('factor'));
  const setActiveForce = (force: ForceId) => setSearchParams({ factor: force });

  // An invalid ?factor= falls back to 'type' - rewrite it so the URL always
  // names the tab that is actually shown (copy/share stays truthful).
  useEffect(() => {
    const raw = searchParams.get('factor');
    if (raw !== null && raw !== activeForce) {
      setSearchParams({ factor: activeForce }, { replace: true });
    }
  }, [searchParams, activeForce, setSearchParams]);

  const selectRelatedForce = (force: ForceId) => {
    setActiveForce(force);
    document.getElementById(`pricing-tab-${force}`)?.focus();
  };

  return (
    <main className="relative min-h-screen bg-surface-card font-inter text-text-primary">
      <div className="container mx-auto px-4 md:px-12 lg:px-24 3xl:px-24 4xl:px-32 pt-16 3xl:pt-20 4xl:pt-24 pb-24 md:pb-16 3xl:pb-20 4xl:pb-24 max-w-7xl">
        {/* Breadcrumb */}
        <nav aria-label="Breadcrumb" className="mb-8 md:mb-12 3xl:mb-10 4xl:mb-12">
          <Link
            to="/"
            className="inline-flex min-h-touch items-center gap-2 3xl:gap-2.5 rounded-lg font-poppins text-sm md:text-base 3xl:text-lg 4xl:text-xl font-semibold text-brand-700 transition-colors duration-200 hover:text-brand-hover focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:w-4.5! md:h-4.5! 3xl:w-5! 3xl:h-5! 4xl:w-6! 4xl:h-6!" />
            <span>Pricing &amp; valuation</span>
          </Link>
        </nav>

        {/* Factor selector */}
        <div className="mb-10 md:mb-12 3xl:mb-14 4xl:mb-16">
          <PricingFactorTabs activeForce={activeForce} onChange={setActiveForce} />
        </div>

        {/* Factor-specific comparison */}
        <PricingExplorer activeForce={activeForce} onForceChange={selectRelatedForce} />
      </div>
      <ScrollToTop />
    </main>
  );
};

export default PricingPage;
