import { useMemo } from "react";
import { useParams } from "react-router-dom";
import { CaseStudyHeader } from "@/components/case-study/CaseStudyHeader";
import { CaseStudyStrengths } from "@/components/case-study/CaseStudyStrengths";
import { ProjectStatistics } from "@/components/case-study/ProjectStatistics";
import { BenefitCard } from "@/components/case-study/BenefitCard";
import { BeforeAfterSlider } from "@/components/case-study/BeforeAfterSlider";
import { ScrollToTop } from "@/components/ui/ScrollToTop";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { getCaseStudyById } from "@/data/caseStudies";

/**
 * Combine an optional overview-map caption and attribution into a single caption,
 * adding a period only when the caption doesn't already end with punctuation.
 */
function formatMapCaption(caption: string | undefined, attribution: string | undefined): string {
  const c = (caption ?? '').trim();
  const a = (attribution ?? '').trim();
  if (!c) return a;
  if (!a) return c;
  return `${c}${/[.!?]$/.test(c) ? ' ' : '. '}${a}`;
}

/**
 * CaseStudyPage component - Displays a detailed project case study by ID
 * Uses the project's Poppins font for headings and Inter font for body text
 * Based on the Figma design with responsive layout
 */
function CaseStudyPage(): JSX.Element {
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

        {/* Hero Image + Strengths */}
        <div className="grid grid-cols-1 lg:grid-cols-[600px_1fr] gap-x-6 lg:gap-x-14 gap-y-4 mb-12 items-stretch">
          <div className="relative rounded-xl overflow-hidden aspect-[3/2] lg:aspect-auto lg:h-full min-h-72 bg-surface-subtle">
            <img
              src={caseStudyData.mainImage}
              srcSet={caseStudyData.mainImageSrcSet}
              sizes="(max-width: 767px) calc(100vw - 48px), (min-width: 768px) and (max-width: 1023px) calc(100vw - 148px), 600px"
              alt={caseStudyData.title}
              className="w-full h-full object-cover"
              loading="eager"
              decoding="async"
              width="960"
              height="640"
              ref={(el) => el?.setAttribute('fetchpriority', 'high')}
            />
          </div>
          <div className="lg:max-w-[480px]">
            <CaseStudyStrengths
              strengths={caseStudyData.strengths}
              sdgs={caseStudyData.sdgs}
              rating={caseStudyData.rating}
              ratingAgency={caseStudyData.ratingAgency}
              ratingNote={caseStudyData.ratingNote}
            />
          </div>
          {caseStudyData.mainImageCaption && (
            <p className="lg:col-span-2 font-inter text-xs text-text-muted leading-normal">
              {caseStudyData.mainImageCaption}
            </p>
          )}
        </div>

        {/* Remote sensing evidence + project overview */}
        {(caseStudyData.overviewMap || (caseStudyData.beforeAfterImages && caseStudyData.beforeAfterImages.length > 0)) && (
          <div className="mb-16">
            <p className="text-xs uppercase text-text-muted font-inter font-semibold leading-snug mb-4">
              Satellite images
            </p>

            {/* Overview map + project summary */}
            {caseStudyData.overviewMap && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 lg:gap-10 items-start mb-10">
                <div className="flex flex-col">
                  <Dialog>
                    <DialogTrigger asChild>
                      <button
                        type="button"
                        className="group relative flex w-full aspect-[4/3] cursor-pointer items-center justify-center overflow-hidden rounded-xl bg-surface-subtle border border-border-ui shadow-sm text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                      >
                        <img
                          src={caseStudyData.overviewMap.image}
                          alt={`${caseStudyData.title} project area overview`}
                          className="block h-full w-full object-cover"
                          loading="lazy"
                          decoding="async"
                        />
                        <span className="absolute bottom-3 right-3 rounded-md bg-black/60 px-2.5 py-1.5 font-inter text-xs font-medium text-white opacity-0 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100">
                          View full map
                        </span>
                      </button>
                    </DialogTrigger>
                    <DialogContent className="max-w-[95vw] max-h-[95vh] border-0 bg-transparent p-0 shadow-none [&>button]:right-3 [&>button]:top-3 [&>button]:rounded-full [&>button]:bg-white [&>button]:p-1.5 [&>button]:text-black [&>button]:hover:bg-white [&>button]:hover:opacity-80 [&>button]:focus-visible:ring-white [&>button]:opacity-100">
                      <DialogTitle className="sr-only">Project boundary map</DialogTitle>
                      <DialogDescription className="sr-only">
                        Full-resolution Sentinel-2 overview of the project boundary.
                      </DialogDescription>
                      <div className="flex max-h-[90vh] max-w-[90vw] items-center justify-center overflow-hidden rounded-lg bg-black p-2">
                        <img
                          src={caseStudyData.overviewMap.image}
                          alt={`${caseStudyData.title} project area overview`}
                          className="block max-h-[88vh] max-w-[88vw] object-contain"
                          loading="lazy"
                          decoding="async"
                        />
                      </div>
                    </DialogContent>
                  </Dialog>
                  {(caseStudyData.overviewMap.caption || caseStudyData.overviewMap.attribution) && (
                    <p className="mt-2 font-inter text-xs text-text-muted leading-normal">
                      {formatMapCaption(caseStudyData.overviewMap.caption, caseStudyData.overviewMap.attribution)}
                    </p>
                  )}
                </div>
                <div className="min-w-0">
                  <h3 className="font-inter text-base font-semibold text-text-primary">
                    Project overview
                  </h3>
                  {caseStudyData.about && (
                    <p className="mt-2 font-inter text-sm text-text-secondary leading-relaxed">
                      {caseStudyData.about}
                    </p>
                  )}
                  <dl className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-3 border-t border-border-ui pt-4 font-inter text-xs">
                    <div>
                      <dt className="font-medium text-text-primary">Location</dt>
                      <dd className="mt-0.5 text-text-secondary leading-snug">{caseStudyData.location}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-text-primary">Duration</dt>
                      <dd className="mt-0.5 text-text-secondary leading-snug">{caseStudyData.duration}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-text-primary">Methodology</dt>
                      <dd className="mt-0.5 text-text-secondary leading-snug">{caseStudyData.methodology}</dd>
                    </div>
                    <div>
                      <dt className="font-medium text-text-primary">Project type</dt>
                      <dd className="mt-0.5 text-text-secondary leading-snug">{caseStudyData.projectType}</dd>
                    </div>
                  </dl>
                </div>
              </div>
            )}

            {/* Before/After village-tract sliders */}
            {caseStudyData.beforeAfterImages && caseStudyData.beforeAfterImages.length > 0 && (
              <div className="mt-2">
                <h3 className="font-inter text-sm font-semibold text-text-primary mb-4">
                  Before & after
                </h3>
                <div className={`grid auto-rows-fr gap-6 ${caseStudyData.beforeAfterImages.length > 1 ? 'grid-cols-1 md:grid-cols-2 lg:grid-cols-3' : 'grid-cols-1'}`}>
                  {caseStudyData.beforeAfterImages.map((image) => (
                    <BeforeAfterSlider
                      key={`${image.before}-${image.after}`}
                      before={image.before}
                      after={image.after}
                      beforeLabel={image.beforeLabel}
                      afterLabel={image.afterLabel}
                      caption={image.caption}
                      aspectClass={caseStudyData.beforeAfterImages.length > 1 ? 'aspect-[4/3]' : 'aspect-video'}
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Gallery Images */}
        {caseStudyData.galleryImages && caseStudyData.galleryImages.length > 0 && (
          <div className="mb-16">
            <p className="text-xs uppercase text-text-muted font-inter font-semibold leading-snug mb-4">Project Gallery</p>
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
        <div className="mb-6 md:mb-12">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-14">
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

        <div className="mb-6 md:mb-12">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-14">
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
}

export default CaseStudyPage;
