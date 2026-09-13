import React from 'react';
import { Check } from 'lucide-react';
import { CASE_STUDY } from '@/lib/colors';
import { SDG_BG_CLASS } from '@/lib/sdg';

interface Strength {
  text: string;
}

interface SDGBadgeProps {
  number: number;
  title: string;
}

const VALID_SDG_NUMBERS: readonly number[] = Array.from({ length: 17 }, (_, i) => i + 1);

const SDGBadge = ({ number, title }: SDGBadgeProps) => {
  const isValid = VALID_SDG_NUMBERS.includes(number);
  return (
    <div
      className={`h-8 3xl:h-10 4xl:h-12 min-w-14 3xl:min-w-16 4xl:min-w-20 rounded-sm flex items-center justify-center px-2 3xl:px-3 ${isValid ? SDG_BG_CLASS[number] : 'bg-neutral-500'}`}
      title={title}
      aria-label={`SDG ${number}: ${title}`}
    >
      <span className="text-white text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-semibold leading-tight">SDG {number}</span>
    </div>
  );
};

interface CaseStudyStrengthsProps {
  strengths: Strength[];
  sdgs: SDGBadgeProps[];
  rating: string;
  ratingAgency: string;
  ratingNote: string;
}

/**
 * Component to display project strengths with checkmarks
 * Matches the Figma design with proper styling and layout
 */
export const CaseStudyStrengths = ({
  strengths,
  sdgs,
  rating,
  ratingAgency,
  ratingNote
}: CaseStudyStrengthsProps) => {
  return (
    <div className="bg-surface-card rounded-2xl p-6 md:p-8 3xl:p-10 4xl:p-12 shadow-sm border border-border-ui h-full w-full min-w-0">
      {/* Header with title + rating */}
      <div className="flex items-start justify-between gap-4 mb-5 3xl:mb-6 4xl:mb-8">
        <h2 className="font-inter text-sm 3xl:text-lg 4xl:text-xl font-semibold text-text-primary">Strengths</h2>
        <div className="flex flex-col items-center gap-1 3xl:gap-1.5 flex-shrink-0">
          <div className="w-9 h-9 3xl:w-11 3xl:h-11 4xl:w-14 4xl:h-14 rounded-full border border-border-ui flex items-center justify-center">
            <span className="text-text-primary text-sm 3xl:text-lg 4xl:text-xl font-inter font-semibold">{rating}</span>
          </div>
          <span className="text-text-primary text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-semibold text-center">{ratingAgency}</span>
        </div>
      </div>

      <div className="flex flex-col gap-4 3xl:gap-5 mb-8 md:mb-10 3xl:mb-12 4xl:mb-14 w-full">
        {strengths.map((strength, index) => (
          <div key={index} className="flex items-start gap-2 3xl:gap-2.5 w-full">
            <div className="flex-shrink-0 flex items-center justify-center w-3.5 h-3.5 3xl:w-5 3xl:h-5 4xl:w-6 4xl:h-6 mt-0.5 3xl:mt-1 text-semantic-success-icon">
              <Check className="w-3 h-3 3xl:w-4 3xl:h-4 4xl:w-5 4xl:h-5 stroke-[3]" />
            </div>
            <span className="font-inter text-xs 3xl:text-base 4xl:text-lg leading-snug 3xl:leading-[1.6] text-text-primary whitespace-normal">{strength.text}</span>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-6 3xl:gap-8">
        <div className="flex flex-wrap gap-2 3xl:gap-3">
          {sdgs.map((s) => (
            <SDGBadge key={s.number} number={s.number} title={s.title} />
          ))}
        </div>

        <div className="text-text-primary text-xs 3xl:text-[15px] 4xl:text-lg font-inter font-semibold leading-snug 3xl:leading-[1.6] break-words">
          {ratingNote}
        </div>
      </div>
    </div>
  );
};
