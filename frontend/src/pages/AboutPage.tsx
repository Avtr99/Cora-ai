import React from "react";
import { Link } from "react-router-dom";
import { IconWrapper } from "@/components/icons/IconWrapper";
import { AgentDiagram } from "@/components/about/AgentDiagram";
import { ScrollToTop } from "../components/ui/ScrollToTop";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg?react";
import UsersIcon from "@/assets/icons/users.svg?react";
import BookIcon from "@/assets/icons/book.svg?react";
import TargetIcon from "@/assets/icons/target.svg?react";
import GlobeIcon from "@/assets/icons/globe.svg?react";
import PricingIcon from "@/assets/icons/pricing.svg?react";
import LightbulbIcon from "@/assets/icons/lightbulb.svg?react";
import { AppFooter } from "@/components/layout/AppFooter";

// Icon mapping for dynamic usage
const iconMap = {
  'users': UsersIcon,
  'book': BookIcon,
  'target': TargetIcon,
  'globe': GlobeIcon,
  'pricing': PricingIcon,
  'lightbulb': LightbulbIcon,
} as const;

const AboutPage: React.FC = () => {
  const featureHighlights = [
    {
      icon: 'users' as keyof typeof iconMap,
      title: 'Advanced AI Agents',
      description:
        'Powered by complex AI agents that deeply understand and accurately interpret complex carbon market concepts.'
    },
    {
      icon: 'book' as keyof typeof iconMap,
      title: 'Comprehensive Knowledge Base',
      description:
        'Verified VCM resources combining regulatory documents, market reports, and industry standards from credible public sources.'
    },
    {
      icon: 'target' as keyof typeof iconMap,
      title: 'Answers That Make Sense',
      description:
        'No more wrestling with jargon or technical complexity. Break down sophisticated VCM concepts into clear, practical explanations tailored to your needs.'
    }
  ];

  const helpTopics = [
    {
      icon: 'book' as keyof typeof iconMap,
      label: 'Understanding complex carbon methodologies'
    },
    {
      icon: 'globe' as keyof typeof iconMap,
      label: 'Navigating international climate policies such as Article 6'
    },
    {
      icon: 'pricing' as keyof typeof iconMap,
      label: 'Understanding pricing factors and drivers'
    },
    {
      icon: 'users' as keyof typeof iconMap,
      label: 'Stakeholder education and training'
    },
    {
      icon: 'lightbulb' as keyof typeof iconMap,
      label: 'Assistance for project development'
    }
  ];

  return (
    <main className="bg-surface-base min-h-screen relative">
      <ScrollToTop />
      <div className="container mx-auto px-4 md:px-12 lg:px-24 pt-16 pb-8 max-w-7xl">
        {/* Header with Back Navigation */}
        <nav aria-label="Page" className="mb-4 md:mb-8">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base font-semibold"
          >
            <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5" />
            <span>About Cora</span>
          </Link>
        </nav>

        {/* Main Page Heading - Visually Hidden but accessible to screen readers */}
        <h1 className="sr-only">About Cora - Voluntary Carbon Market Educational AI Assistant</h1>

        {/* Content */}
        <div className="space-y-8 md:space-y-16">
          {/* Introduction */}
          <section className="max-w-3xl">
            <h2 className="font-poppins text-lg md:text-xl font-semibold leading-[24px] md:leading-[28px] text-text-primary mb-2 md:mb-4">
              Democratizing Carbon Market Knowledge
            </h2>
            <p className="font-inter text-sm md:text-base leading-[22px] md:leading-[26px] text-text-secondary">
              Cora is an educational AI assistant for the VCM developed as part of a research project. Cora makes complex VCM concepts accessible to project developers, investors, researchers, and policy makers worldwide.
            </p>
          </section>

          {/* Highlights and Assistance */}
          <section className="flex flex-col gap-6 md:gap-10 lg:flex-row">
            <div className="flex-1 space-y-4 md:space-y-7">
              {featureHighlights.map(({ icon, title, description }) => (
                <div key={title} className="flex items-start gap-3 md:gap-4">
                  <div className="flex h-10 w-10 md:h-12 md:w-12 flex-shrink-0 items-center justify-center rounded-md bg-brand-100 text-brand-500">
                    <IconWrapper Icon={iconMap[icon]} size={18} color="currentColor" className="md:!w-[22px] md:!h-[22px]" />
                  </div>
                  <div className="space-y-1">
                    <h3 className="font-poppins text-sm md:text-base font-semibold leading-[20px] md:leading-[24px] text-brand-900">
                      {title}
                    </h3>
                    <p className="font-inter text-xs md:text-sm leading-[18px] md:leading-[22px] text-text-secondary">
                      {description}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex-1">
              <div className="rounded-xl md:rounded-2xl border border-border-ui bg-surface-card p-4 md:p-8">
                <h3 className="font-poppins text-base md:text-lg font-semibold leading-[22px] md:leading-[26px] text-brand-900 mb-4 md:mb-6">
                  What Cora can help you with?
                </h3>
                <ul className="space-y-3 md:space-y-4">
                  {helpTopics.map(({ icon, label }) => (
                    <li key={label} className="flex items-start gap-3 md:gap-4">
                      <span className="flex h-5 w-5 flex-shrink-0 items-center justify-center mt-0.5">
                        <IconWrapper Icon={iconMap[icon]} size={18} className="md:!w-[20px] md:!h-[20px]" />
                      </span>
                      <span className="font-inter text-sm md:text-base leading-[20px] md:leading-[24px] text-brand-900">
                        {label}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </section>

          {/* How the AI Assistant Works */}
          <section>
            <h3 className="font-poppins text-lg md:text-xl font-semibold leading-[24px] md:leading-[28px] text-text-primary mb-2 md:mb-4">
              How the AI assistant works
            </h3>
            <div className="pt-1 md:pt-2 pb-0">
              <AgentDiagram />
            </div>
          </section>
        </div>

        {/* Footer */}
        <AppFooter />
      </div>
    </main>
  );
};

export default AboutPage;
