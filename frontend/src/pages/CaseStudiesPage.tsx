import React from "react";
import { Link } from "react-router-dom";
import { ScrollToTop } from "@/components/ui/ScrollToTop";
import { LensBadge } from "@/components/ui/LensBadge";
import { caseStudies } from "@/data/caseStudies";
import { IconWrapper } from "@/components/icons/IconWrapper";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg?react";
import { CASE_STUDY } from "@/lib/colors";

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
  sdgs: Array<{ number: number; bgColor: string }>;
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
    <article className="rounded-xl border border-border-ui bg-surface-card overflow-hidden">
      <div className="flex flex-col md:flex-row">
        {/* Image */}
        <div className="w-full md:w-[42%] relative bg-surface-subtle aspect-[16/10] md:aspect-[16/10] md:min-h-[300px]">
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
        <div className="w-full md:w-[58%] p-5 md:p-8 flex flex-col">
          {/* Badges row */}
          <div className="flex flex-wrap items-center gap-2 mb-5">
            <LensBadge label={lensLabel} />
            <span
              className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold"
              style={{ backgroundColor: CASE_STUDY.rating.bg, color: CASE_STUDY.rating.text }}
            >
              {ratingAgency} {rating}
            </span>
          </div>

          {/* Title — dominant */}
          <h2 className="font-inter text-lg md:text-2xl font-semibold text-text-primary leading-[1.25] mb-3">
            {title}
          </h2>

          {/* Org + ID — strong, scannable */}
          <div className="flex items-center gap-2 mb-1 text-sm font-inter">
            <span className="text-text-secondary">{organization}</span>
            <span className="text-text-muted">·</span>
            <span className="text-text-secondary">{organizationId}</span>
          </div>

          {/* Location + Duration — secondary */}
          <p className="text-xs text-text-muted font-inter mb-4">
            {location} · {duration}
          </p>

          {/* Project type — pill tag */}
          <span
            className="inline-flex self-start px-2.5 py-1 rounded-md text-xs font-semibold mb-4"
            style={{ backgroundColor: CASE_STUDY.type.bg, color: CASE_STUDY.type.text }}
          >
            {projectType}
          </span>

          {/* Summary — readable body text */}
          <p className="text-sm text-text-secondary font-inter leading-[1.7] mb-6" style={{ textWrap: 'pretty' }}>
            {summary}
          </p>

          {/* Footer bar */}
          <div className="mt-auto flex items-center justify-between pt-4 border-t border-surface-subtle">
            <div className="flex items-center gap-2">
              <span className="text-xs uppercase tracking-wider text-text-muted font-inter font-semibold">SDGs</span>
              {sdgs.map((sdg) => (
                <div
                  key={sdg.number}
                  className="w-[28px] h-[28px] rounded-full flex items-center justify-center text-white text-xs font-bold text-center leading-none"
                  style={{ backgroundColor: sdg.bgColor }}
                  title={`SDG ${sdg.number}`}
                  aria-label={`SDG ${sdg.number}`}
                >
                  {sdg.number}
                </div>
              ))}
            </div>
            <Link
              to={`/case-study/${id}`}
              className="inline-flex items-center gap-1.5 text-brand-700 font-poppins text-sm font-semibold hover:text-brand-hover transition-colors duration-200"
            >
              Read case study
              <span aria-hidden="true" className="text-base">→</span>
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

      <div className="container mx-auto px-4 md:px-12 lg:px-24 pt-16 pb-8 max-w-7xl">
        {/* Page Header */}
        <header className="mb-8 md:mb-12">
          <nav aria-label="Back navigation" className="mb-4 md:mb-8">
            <Link
              to="/"
              className="inline-flex items-center gap-2 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base font-semibold"
            >
              <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5" />
              <span>Case studies</span>
            </Link>
          </nav>
          <h1 className="sr-only">Case Studies - Voluntary Carbon Market</h1>
          <p className="font-inter text-sm md:text-base leading-[22px] md:leading-[26px] text-text-secondary max-w-[640px]">
            Deep dives into real carbon credit projects. Each case study breaks down methodology,
            co-benefits, risks, and what makes a project high-quality.
          </p>
        </header>

        {/* Cards */}
        <div className="flex flex-col gap-6 md:gap-8">
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
