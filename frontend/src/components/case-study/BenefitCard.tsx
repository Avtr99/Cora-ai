import React from 'react';
import { CASE_STUDY } from '@/lib/colors';

interface BenefitCardProps {
  number: number;
  title: string;
  description: string;
}

/**
 * Card component for displaying project benefits
 * Matches the Figma design with proper styling and layout
 */
export const BenefitCard = ({
  number,
  title,
  description
}: BenefitCardProps) => {
  return (
    <div className="bg-surface-card rounded-2xl p-5 md:p-10 shadow-sm border border-border-ui w-full h-full">
      <div className="flex flex-col gap-3 md:gap-8">
        <div>
          <span className="font-poppins" style={{ color: CASE_STUDY.type.text }}>
            <span className="text-2xl md:text-3xl font-semibold">{number} </span>
            <span className="text-base md:text-xl font-normal">{title}</span>
          </span>
        </div>
        <p className="font-inter text-sm md:text-base leading-[22px] md:leading-[26px] text-text-primary" style={{ textWrap: 'pretty' }}>{description}</p>
      </div>
    </div>
  );
};
