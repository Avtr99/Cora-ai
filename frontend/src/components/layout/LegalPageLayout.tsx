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
      <div className="container mx-auto px-4 md:px-12 lg:px-24 pt-16 pb-8 max-w-4xl">
        {/* Header with Back Navigation */}
        <nav aria-label="Page" className="mb-4 md:mb-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base font-semibold"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5" />
            <span>Back to Cora</span>
          </Link>
        </nav>

        {/* Page Title */}
        <div className="mb-8 md:mb-12">
          <h1 className="font-poppins text-2xl md:text-3xl font-bold leading-[32px] md:leading-[38px] text-text-primary">
            {title}
          </h1>
          <p className="font-inter text-xs md:text-sm text-text-muted mt-2">
            Last updated: {lastUpdated}
          </p>
        </div>

        {/* Content */}
        <div className="space-y-8 md:space-y-10">
          {children}
        </div>

        {/* Footer */}
        <AppFooter />
      </div>
    </main>
  );
};

export default LegalPageLayout;
