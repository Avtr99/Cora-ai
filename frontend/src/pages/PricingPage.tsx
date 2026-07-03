import React, { useState, lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import PricingDrivers from "../components/pricing/PricingDrivers";
import MethodologyExplanation from "../components/pricing/MethodologyExplanation";
import SBTImpact from "../components/pricing/SBTImpact";
import { ScrollToTop } from "../components/ui/ScrollToTop";
import { IconWrapper } from "@/components/icons/IconWrapper";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg?react";

// Lazy-load the chart component since Recharts is very large (1.2MB)
const PricingChart = lazy(() => import("../components/pricing/PricingChart"));

// Loading skeleton for the chart
const ChartSkeleton = () => (
  <div className="bg-surface-card rounded-2xl p-6 h-[400px] animate-pulse">
    <div className="h-6 bg-surface-subtle rounded w-1/3 mb-4"></div>
    <div className="h-8 bg-surface-subtle rounded w-1/4 mb-6"></div>
    <div className="h-[280px] bg-surface-subtle rounded"></div>
  </div>
);

const PricingPage: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>("Agriculture");
  const pageData = {
    title: "Carbon Credit Pricing Analysis",
    context: "Voluntary Carbon Market"
  };
  
  return (
    <main className="bg-surface-page min-h-screen relative">
      {/* Main Page Heading - Visually Hidden but accessible to screen readers */}
      <h1 className="sr-only">{`${pageData.title} - ${pageData.context}`}</h1>
      
      <div className="container mx-auto px-4 md:px-12 lg:px-24 pt-16 pb-8 max-w-7xl">
        <nav aria-label="Back navigation" className="mb-4 md:mb-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base font-semibold"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5" />
            <span>Understanding pricing</span>
          </Link>
        </nav>

        {/* First section - Chart and Methodology side by side */}
        <div className="mb-6 md:mb-12 flex flex-col lg:flex-row gap-4 lg:gap-6 items-stretch">
          <div className="w-full lg:w-[65%] min-w-0">
            <Suspense fallback={<ChartSkeleton />}>
              <PricingChart
                selectedCategory={selectedCategory}
                onCategoryChange={setSelectedCategory}
              />
            </Suspense>
          </div>

          <div className="w-full lg:w-[35%] min-w-0">
            <MethodologyExplanation category={selectedCategory} />
          </div>
        </div>

        {/* Second section - Pricing Drivers */}
        <div className="mb-6 md:mb-12">
          <PricingDrivers category={selectedCategory} />
        </div>

        {/* Third section - SBT Impact */}
        <div>
          <SBTImpact category={selectedCategory} />
        </div>
      </div>
      <ScrollToTop />
    </main>
  );
};

export default PricingPage;
