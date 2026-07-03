import React, { useMemo } from "react";
import { useParams } from "react-router-dom";
import { CaseStudyHeader } from "@/components/case-study/CaseStudyHeader";
import { CaseStudyStrengths } from "@/components/case-study/CaseStudyStrengths";
import { ProjectDetails } from "@/components/case-study/ProjectDetails";
import { ProjectStatistics } from "@/components/case-study/ProjectStatistics";
import { BenefitCard } from "@/components/case-study/BenefitCard";
import { ScrollToTop } from "@/components/ui/ScrollToTop";
import { getCaseStudyById } from "@/data/caseStudies";

/**
 * CaseStudyPage component - Displays a detailed project case study by ID
 * Uses the project's Poppins font for headings and Inter font for body text
 * Based on the Figma design with responsive layout
 */
const CaseStudyPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const caseStudyData = id ? getCaseStudyById(id) : undefined;

  const firstTwoBenefits = useMemo(() => caseStudyData?.benefits.slice(0, 2) ?? [], [caseStudyData?.benefits]);
  const lastTwoBenefits = useMemo(() => caseStudyData?.benefits.slice(2, 4) ?? [], [caseStudyData?.benefits]);

  if (!caseStudyData) {
    return (
      <main className="bg-surface-page min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-semibold text-text-primary mb-2">Case study not found</h1>
          <p className="text-text-muted">The requested case study does not exist.</p>
        </div>
      </main>
    );
  }

  return (
    <main className="bg-surface-page min-h-screen">
      <ScrollToTop />

      {/* Main Page Heading - Visually Hidden but accessible to screen readers */}
      <h1 className="sr-only">Carbon Credit Project Case Study - {caseStudyData.title}</h1>

      <div className="container mx-auto px-4 md:px-16 lg:px-24 pt-16 pb-8 max-w-7xl">
        {/* Case Study Header */}
        <CaseStudyHeader
          title={caseStudyData.title}
          organization={caseStudyData.organization}
          organizationId={caseStudyData.organizationId}
          registryUrl={caseStudyData.registryUrl}
          lensLabel={caseStudyData.lensLabel}
          tags={caseStudyData.tags}
        />

        {/* Main Image and Strengths */}
        <div className="flex flex-col lg:flex-row gap-6 lg:gap-[55px] mb-[48px]">
          <div className="lg:w-[600px] relative rounded-xl overflow-hidden aspect-[13/8] md:aspect-auto md:h-[400px] bg-surface-subtle">
            <img
              src={caseStudyData.mainImage}
              srcSet={caseStudyData.mainImageSrcSet}
              sizes="(max-width: 767px) calc(100vw - 48px), (min-width: 768px) and (max-width: 1023px) calc(100vw - 148px), 600px"
              alt={caseStudyData.title}
              className="w-full h-full object-cover"
              loading="eager"
              ref={(el) => el?.setAttribute('fetchpriority', 'high')}
              decoding="async"
              width="600"
              height="400"
            />
          </div>
          <div className="lg:flex-1 lg:max-w-[480px] relative">
            <CaseStudyStrengths
              strengths={caseStudyData.strengths}
              sdgs={caseStudyData.sdgs}
              rating={caseStudyData.rating}
              ratingAgency={caseStudyData.ratingAgency}
              ratingNote={caseStudyData.ratingNote}
            />
          </div>
        </div>

        {/* Project Details */}
        <ProjectDetails
          type={caseStudyData.projectType}
          location={caseStudyData.location}
          duration={caseStudyData.duration}
          reductionRemoval={caseStudyData.reductionRemoval}
          methodology={caseStudyData.methodology}
          about={caseStudyData.about}
          mapImage={caseStudyData.mapImage}
          mapImageSrcSet={caseStudyData.mapImageSrcSet}
          mapImageSizes={caseStudyData.mapImageSizes}
          mapSource={caseStudyData.mapSource}
          projectImages={caseStudyData.projectImages}
        />

        {/* Gallery Images */}
        {caseStudyData.galleryImages && caseStudyData.galleryImages.length > 0 && (
          <div className="mb-16">
            <p className="text-xs uppercase text-text-muted font-inter font-semibold leading-[17px] mb-4">Project Gallery</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {caseStudyData.galleryImages.map((img, i) => (
                <div key={i} className="relative aspect-[4/3] overflow-hidden rounded-xl bg-surface-subtle border border-border-ui shadow-sm">
                  <img
                    src={img}
                    alt={`${caseStudyData.title} - gallery image ${i + 1}`}
                    className="w-full h-full object-cover"
                    loading="lazy"
                    decoding="async"
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Project Statistics */}
        <ProjectStatistics
          carbonSequestered={caseStudyData.statistics.carbonSequestered}
          permanenceRisk={caseStudyData.statistics.permanenceRisk}
          bufferPool={caseStudyData.statistics.bufferPool}
          creditsIssued={caseStudyData.statistics.creditsIssued}
          creditsRetired={caseStudyData.statistics.creditsRetired}
          source={caseStudyData.statistics.source}
        />

        {/* Project Benefits */}
        <div className="mb-6 md:mb-[46px]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-[55px]">
            {firstTwoBenefits.map((benefit) => (
              <BenefitCard
                key={benefit.number}
                number={benefit.number}
                title={benefit.title}
                description={benefit.description}
              />
            ))}
          </div>
        </div>

        <div className="mb-6 md:mb-[46px]">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-[55px]">
            {lastTwoBenefits.map((benefit) => (
              <BenefitCard
                key={benefit.number}
                number={benefit.number}
                title={benefit.title}
                description={benefit.description}
              />
            ))}
          </div>
        </div>
      </div>
    </main>
  );
};

export default CaseStudyPage;
