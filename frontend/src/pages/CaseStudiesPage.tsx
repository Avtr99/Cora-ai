import React from "react";
import { Link } from "react-router-dom";
import { ScrollToTop } from "@/components/ui/ScrollToTop";
import { LensBadge } from "@/components/ui/LensBadge";
import { caseStudies } from "@/data/caseStudies";
import { IconWrapper } from "@/components/icons/IconWrapper";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg?react";
import { CASE_STUDY } from "@/lib/colors";
import { SDG_BG_CLASS } from "@/lib/sdg";
import type { SDG } from "@/data/caseStudyTypes";

interface CaseStudyCardProps {
  id: string;
  title: string;
  organization: string;
  organizationId: string;
  location: string;
  duration: string;
  projectType: string;
  lensLabel: string;
  summary: string;
  mainImage: string;
  mainImageSrcSet?: string;
  rating: string;
  ratingAgency: string;
  sdgs: SDG[];
}

const CaseStudyCard: React.FC<CaseStudyCardProps> = ({
  id,
  title,
  organization,
  organizationId,
  location,
  duration,
  projectType,
  lensLabel,
  summary,
  mainImage,
  mainImageSrcSet,
  rating,
  ratingAgency,
  sdgs,
}) => {
  return (
    <article className="rounded-xl 3xl:rounded-2xl 4xl:rounded-2xl border border-border-ui bg-surface-card overflow-hidden">
      <div className="flex flex-col md:flex-row">
        {/* Image */}
        <div className="w-full md:w-[42%] relative bg-surface-subtle aspect-[16/10] md:aspect-[16/10] md:min-h-[300px] 3xl:min-h-[360px] 4xl:min-h-[420px]">
          <img
            src={mainImage}
            srcSet={mainImageSrcSet}
            sizes="(max-width: 767px) calc(100vw - 48px), 42vw"
            alt={title}
            className="w-full h-full object-cover"
            loading="lazy"
            decoding="async"
          />
        </div>

        {/* Content */}
        <div className="w-full md:w-[58%] p-5 md:p-8 3xl:p-10 4xl:p-12 flex flex-col">
          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-2 3xl:gap-3 4xl:gap-3 mb-5 3xl:mb-6 4xl:mb-7">
            <LensBadge label={lensLabel} />
            <span
              className="inline-flex items-center px-2.5 py-1 3xl:px-3.5 3xl:py-1.5 4xl:px-4 4xl:py-2 rounded-full text-xs 3xl:text-[15px] 4xl:text-[17px] font-semibold"
              style={{ backgroundColor: CASE_STUDY.rating.bg, color: CASE_STUDY.rating.text }}
            >
              {ratingAgency} {rating}
            </span>
          </div>

          {/* Title — dominant */}
          <h2 className="font-inter text-heading-3 md:text-heading-2 3xl:text-2xl 4xl:text-3xl font-semibold text-text-primary leading-tight mb-3 3xl:mb-4 4xl:mb-5">
            {title}
          </h2>

          {/* Org + ID — strong, scannable */}
          <div className="flex items-center gap-2 3xl:gap-2.5 mb-1 text-sm 3xl:text-[17px] 4xl:text-xl font-inter">
            <span className="text-text-secondary">{organization}</span>
            <span className="text-text-muted">·</span>
            <span className="text-text-secondary">{organizationId}</span>
          </div>

          {/* Location + Duration — secondary */}
          <p className="text-xs 3xl:text-[15px] 4xl:text-lg text-text-muted font-inter mb-4 3xl:mb-5 4xl:mb-6">
            {location} · {duration}
          </p>

          {/* Project type — pill tag */}
          <span
            className="inline-flex self-start px-2.5 py-1 3xl:px-3.5 3xl:py-1.5 4xl:px-4 4xl:py-2 rounded-md text-xs 3xl:text-[15px] 4xl:text-[17px] font-semibold mb-4 3xl:mb-5 4xl:mb-6"
            style={{ backgroundColor: CASE_STUDY.type.bg, color: CASE_STUDY.type.text }}
          >
            {projectType}
          </span>

          {/* Summary — readable body text */}
          <p className="text-sm 3xl:text-[17px] 4xl:text-[22px] text-text-secondary font-inter leading-[1.7] 3xl:leading-[1.6] mb-6 3xl:mb-8 4xl:mb-10" style={{ textWrap: 'pretty' }}>
            {summary}
          </p>

          {/* Footer bar */}
          <div className="mt-auto flex flex-col gap-4 pt-5 3xl:pt-6 4xl:pt-8 border-t border-surface-subtle md:flex-row md:items-center md:justify-between md:gap-3">
            <div className="flex flex-wrap items-center gap-2 3xl:gap-2.5 4xl:gap-3">
              <span className="text-xs 3xl:text-[15px] 4xl:text-lg uppercase tracking-wider text-text-muted font-inter font-semibold">SDGs</span>
              {sdgs.map((sdg) => (
                <div
                  key={sdg.number}
                  className={`w-7 h-7 3xl:w-9 3xl:h-9 4xl:w-11 4xl:h-11 rounded-full flex items-center justify-center text-white text-xs 3xl:text-[15px] 4xl:text-lg font-bold text-center leading-none ${SDG_BG_CLASS[sdg.number] ?? 'bg-neutral-500'}`}
                  title={`SDG ${sdg.number}: ${sdg.title}`}
                  aria-label={`SDG ${sdg.number}: ${sdg.title}`}
                >
                  {sdg.number}
                </div>
              ))}
            </div>
            <Link
              to={`/case-study/${id}`}
              className="flex md:inline-flex items-center justify-center md:justify-start gap-2 3xl:gap-3 w-full md:w-auto min-h-11 md:min-h-0 px-4 py-3 md:px-0 md:py-0 rounded-lg md:rounded-none border border-border-ui md:border-0 bg-surface-subtle md:bg-transparent text-brand-700 font-poppins text-sm 3xl:text-[17px] 4xl:text-xl font-semibold hover:bg-surface-base md:hover:bg-transparent hover:text-brand-hover transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2"
            >
              Read case study
              <span aria-hidden="true" className="text-base 3xl:text-[17px] 4xl:text-xl">→</span>
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
};

const CaseStudiesPage: React.FC = () => {
  return (
    <main className="bg-surface-page min-h-screen">
      <ScrollToTop />

      <div className="container mx-auto px-4 md:px-12 lg:px-24 3xl:px-24 4xl:px-32 pt-16 3xl:pt-20 4xl:pt-24 pb-24 md:pb-16 3xl:pb-20 4xl:pb-24 max-w-7xl 3xl:max-w-[1600px] 4xl:max-w-[1800px]">
        {/* Page Header */}
        <header className="mb-8 md:mb-12 3xl:mb-14 4xl:mb-16">
          <nav aria-label="Back navigation" className="mb-4 md:mb-8 3xl:mb-10 4xl:mb-12">
            <Link
              to="/"
              className="inline-flex items-center gap-2 3xl:gap-2.5 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base 3xl:text-lg 4xl:text-xl font-semibold"
            >
              <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5 3xl:!w-5 3xl:!h-5 4xl:!w-6 4xl:!h-6" />
              <span>Case studies</span>
            </Link>
          </nav>
          <h1 className="sr-only">Case Studies - Voluntary Carbon Market</h1>
          <p className="font-inter text-sm md:text-base 3xl:text-xl 4xl:text-2xl leading-[22px] md:leading-[26px] 3xl:leading-[30px] 4xl:leading-9 text-text-secondary max-w-[640px] 3xl:max-w-[800px] 4xl:max-w-[960px]">
            Deep dives into real carbon credit projects. Each case study breaks down methodology,
            co-benefits, risks, and what makes a project high-quality.
          </p>
        </header>

        {/* Cards */}
        <div className="flex flex-col gap-6 md:gap-8 3xl:gap-10 4xl:gap-12">
          {caseStudies.map((cs) => (
            <CaseStudyCard
              key={cs.id}
              id={cs.id}
              title={cs.title}
              organization={cs.organization}
              organizationId={cs.organizationId}
              location={cs.location}
              duration={cs.duration}
              projectType={cs.projectType}
              lensLabel={cs.lensLabel}
              summary={cs.summary}
              mainImage={cs.mainImage}
              mainImageSrcSet={cs.mainImageSrcSet}
              rating={cs.rating}
              ratingAgency={cs.ratingAgency}
              sdgs={cs.sdgs}
            />
          ))}
        </div>
      </div>
    </main>
  );
};

export default CaseStudiesPage;
