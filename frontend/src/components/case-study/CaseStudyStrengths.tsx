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
      className={`h-8 min-w-14 rounded-sm flex items-center justify-center px-2 ${isValid ? SDG_BG_CLASS[number] : 'bg-neutral-500'}`}
      title={title}
      aria-label={`SDG ${number}: ${title}`}
    >
      <span className="text-white text-xs font-inter font-semibold leading-tight">SDG {number}</span>
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
    <div className="bg-surface-card rounded-2xl p-6 md:p-8 shadow-sm border border-border-ui h-full w-full">
      {/* Header with title + rating */}
      <div className="flex items-start justify-between gap-4 mb-5">
        <h2 className="font-inter text-sm font-semibold text-text-primary">Strengths</h2>
        <div className="flex flex-col items-center gap-1 flex-shrink-0">
          <div className="w-9 h-9 rounded-full border border-border-ui flex items-center justify-center">
            <span className="text-text-primary text-sm font-inter font-semibold">{rating}</span>
          </div>
          <span className="text-text-primary text-xs font-inter font-semibold text-center">{ratingAgency}</span>
        </div>
      </div>

      <div className="flex flex-col gap-4 mb-8 md:mb-10 w-full">
        {strengths.map((strength, index) => (
          <div key={index} className="flex items-start gap-2 w-full">
            <div className="flex-shrink-0 flex items-center justify-center w-3.5 h-3.5 mt-0.5 text-semantic-success-icon">
              <Check className="w-3 h-3 stroke-[3]" />
            </div>
            <span className="font-inter text-xs leading-snug text-text-primary whitespace-normal">{strength.text}</span>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-6">
        <div className="flex flex-wrap gap-2">
          {sdgs.map((s) => (
            <SDGBadge key={s.number} number={s.number} title={s.title} />
          ))}
        </div>

        <div className="text-text-primary text-xs font-inter font-semibold leading-none">
          {ratingNote}
        </div>
      </div>
    </div>
  );
};
