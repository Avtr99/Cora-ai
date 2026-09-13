import React from 'react';
import { Link } from 'react-router-dom';
import { IconWrapper } from '@/components/icons/IconWrapper';
import { ScrollToTop } from '@/components/ui/ScrollToTop';
import { AppFooter } from '@/components/layout/AppFooter';
import ChevronLeftIcon from '@/assets/icons/chevron-left.svg?react';

interface LegalPageLayoutProps {
  title: string;
  lastUpdated: string;
  children: React.ReactNode;
}

/**
 * Shared layout for legal/policy pages (Privacy Policy, Terms of Service, etc.).
 * Provides consistent navigation, heading, and footer structure.
 */
const LegalPageLayout: React.FC<LegalPageLayoutProps> = ({ title, lastUpdated, children }) => {
  return (
    <main className="bg-surface-base min-h-screen relative">
      <ScrollToTop />
      <div className="container mx-auto px-4 md:px-12 lg:px-24 3xl:px-24 4xl:px-32 pt-16 3xl:pt-20 4xl:pt-24 pb-8 3xl:pb-12 4xl:pb-16 max-w-[1320px] 3xl:max-w-[1600px] 4xl:max-w-[1800px]">
        {/* Header with Back Navigation */}
        <nav aria-label="Page" className="mb-4 md:mb-8 3xl:mb-10 4xl:mb-12">
          <Link
            to="/"
            className="inline-flex items-center gap-2 3xl:gap-2.5 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base 3xl:text-lg 4xl:text-xl font-semibold"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5 3xl:!w-5 3xl:!h-5 4xl:!w-6 4xl:!h-6" />
            <span>Back to Cora</span>
          </Link>
        </nav>

        {/* Page Title */}
        <div className="mb-8 md:mb-12">
          <h1 className="font-poppins text-2xl md:text-3xl 3xl:text-4xl 4xl:text-5xl font-bold leading-8 md:leading-9 3xl:leading-10 4xl:leading-11 text-text-primary">
            {title}
          </h1>
          <p className="font-inter text-xs md:text-sm 3xl:text-sm 4xl:text-base text-text-muted mt-2">
            Last updated: {lastUpdated}
          </p>
        </div>

        {/* Content */}
        <div className="space-y-8 md:space-y-10 3xl:space-y-12 4xl:space-y-14">
          {children}
        </div>

        {/* Footer */}
        <AppFooter />
      </div>
    </main>
  );
};

export default LegalPageLayout;
