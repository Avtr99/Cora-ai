import React, { useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { motion, useReducedMotion } from 'framer-motion';
import { ScrollToTop } from '../components/ui/ScrollToTop';
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChevronLeftIcon from '@/assets/icons/chevron-left.svg?react';
import PricingFactorTabs from '@/components/pricing/PricingFactorTabs';
import PricingExplorer from '@/components/pricing/PricingExplorer';
import { FORCE_ORDER, type ForceId } from '@/data/pricingData';
import { FORCE_HEADLINE_STAT } from '@/data/pricingFactorContent';

const parseFactorParam = (value: string | null): ForceId =>
  FORCE_ORDER.includes(value as ForceId) ? (value as ForceId) : 'type';

const PricingPage: React.FC = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const activeForce = parseFactorParam(searchParams.get('factor'));
  const setActiveForce = (force: ForceId) => setSearchParams({ factor: force });
  const reduceMotion = useReducedMotion();

  // An invalid ?factor= falls back to 'type' - rewrite it so the URL always
  // names the tab that is actually shown (copy/share stays truthful).
  useEffect(() => {
    const raw = searchParams.get('factor');
    if (raw !== null && raw !== activeForce) {
      setSearchParams({ factor: activeForce }, { replace: true });
    }
  }, [searchParams, activeForce, setSearchParams]);
  const heroStat = FORCE_HEADLINE_STAT[activeForce];

  const selectRelatedForce = (force: ForceId) => {
    setActiveForce(force);
    document.getElementById(`pricing-tab-${force}`)?.focus();
  };

  return (
    <main className="relative min-h-screen bg-surface-card font-inter text-text-primary">
      <div className="container mx-auto px-4 md:px-12 lg:px-24 3xl:px-24 4xl:px-32 pt-16 3xl:pt-20 4xl:pt-24 pb-24 md:pb-16 3xl:pb-20 4xl:pb-24 max-w-7xl 3xl:max-w-[1600px] 4xl:max-w-[1800px]">
        {/* Breadcrumb */}
        <nav aria-label="Breadcrumb" className="mb-8 md:mb-12 3xl:mb-10 4xl:mb-12">
          <Link
            to="/"
            className="inline-flex min-h-touch items-center gap-2 3xl:gap-2.5 rounded-lg font-poppins text-sm md:text-base 3xl:text-lg 4xl:text-xl font-semibold text-brand-700 transition-colors duration-200 hover:text-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5 3xl:!w-5 3xl:!h-5 4xl:!w-6 4xl:!h-6" />
            <span>Pricing &amp; valuation</span>
          </Link>
        </nav>

        {/* Hero */}
        <header className="mb-10 grid items-end gap-8 md:mb-12 lg:grid-cols-[minmax(0,1fr)_auto]">
          <div className="max-w-3xl">
            <h1 className="text-balance font-poppins text-xl font-semibold text-text-primary md:text-display 3xl:text-4xl">
              How carbon credit prices are set
            </h1>
            <p className="mt-3 max-w-[65ch] text-pretty font-inter text-body-sm md:text-body 3xl:text-lg 4xl:text-xl text-text-secondary">
              Prices in the VCM vary from a few dollars to well over a hundred. A few
              factors explain much of that spread; project size, geography, buyer type,
              and delivery terms also move prices. Prices shown are 2024 transaction
              averages.
            </p>
          </div>
          <dl className="shrink-0 lg:pb-1 lg:text-right" data-testid="pricing-hero-stat">
            <motion.div
              key={activeForce}
              initial={reduceMotion ? false : { opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, ease: [0.4, 0, 0.2, 1] }}
            >
              <dd
                className="font-inter font-semibold leading-none tracking-tight text-text-primary tabular-nums text-xl sm:text-2xl 3xl:text-3xl 4xl:text-3xl"
              >
                {heroStat.value}
              </dd>
              <dt className="mt-1 max-w-[26ch] font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-secondary lg:ml-auto lg:mt-2">{heroStat.caption}</dt>
            </motion.div>
          </dl>
        </header>

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
