import React from 'react';
import { useNavigate } from 'react-router-dom';
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChevronLeftIcon from '@/assets/icons/chevron-left.svg?react';
import { LensBadge } from '@/components/ui/LensBadge';
import { getShortProjectName } from '@/lib/utils';

interface CaseStudyHeaderProps {
  title: string;
  organization: string;
  organizationId: string;
  registryUrl: string;
  lensLabel: string;
  tags: string[];
}

/**
 * Header component for case study pages with back navigation and title
 * Matches the Figma design with proper typography and spacing
 */
export const CaseStudyHeader = ({
  title,
  organization,
  organizationId,
  registryUrl,
  lensLabel,
  tags
}: CaseStudyHeaderProps) => {
  const navigate = useNavigate();
  const shortProjectName = getShortProjectName(title);

  return (
    <div>
      <div className="mb-8 3xl:mb-10 4xl:mb-12">
        <button
          type="button"
          onClick={() => navigate(-1)}
          className="inline-flex items-center gap-2 3xl:gap-2.5 text-brand-700 transition-colors duration-200 hover:text-brand-hover font-poppins text-sm md:text-base 3xl:text-lg 4xl:text-xl font-semibold bg-transparent border-none p-0 cursor-pointer"
          aria-label={`Back to previous page`}
        >
          <IconWrapper Icon={ChevronLeftIcon} size={16} color="currentColor" aria-hidden={true} className="md:!w-4.5 md:!h-4.5 3xl:!w-5 3xl:!h-5 4xl:!w-6 4xl:!h-6" />
          {shortProjectName}
        </button>
      </div>

      <div className="flex flex-col gap-2 md:gap-2.5 3xl:gap-3 mb-8 3xl:mb-10 4xl:mb-12">
        <h1 className="font-inter text-base md:text-base 3xl:text-[28px] 4xl:text-[32px] leading-tight md:leading-[22px] 3xl:leading-[36px] 4xl:leading-[42px] font-semibold text-neutral-900 w-full">
          {title}
        </h1>
        
        <div className="flex flex-wrap items-center gap-2 3xl:gap-3">
          <a href={registryUrl} target="_blank" rel="noopener noreferrer" className="text-text-secondary font-inter text-xs md:text-sm 3xl:text-[17px] 4xl:text-xl underline whitespace-normal break-words min-w-0">
            {organization} · {organizationId}
          </a>
          
          <LensBadge label={lensLabel} />
        </div>
      </div>
    </div>
  );
};
