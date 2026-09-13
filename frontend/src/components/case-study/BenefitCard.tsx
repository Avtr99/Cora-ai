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
    <div className="bg-surface-card rounded-2xl p-5 md:p-10 3xl:p-12 4xl:p-14 shadow-sm border border-border-ui w-full h-full">
      <div className="flex flex-col gap-3 md:gap-8 3xl:gap-10 4xl:gap-12">
        <div>
          <span className="font-poppins" style={{ color: CASE_STUDY.type.text }}>
            <span className="text-2xl md:text-3xl 3xl:text-4xl 4xl:text-5xl font-semibold">{number} </span>
            <span className="text-base md:text-xl 3xl:text-2xl 4xl:text-[28px] font-normal">{title}</span>
          </span>
        </div>
        <p className="font-inter text-sm md:text-base 3xl:text-[17px] 4xl:text-[22px] leading-[22px] md:leading-[26px] 3xl:leading-[1.6] 4xl:leading-[1.6] text-text-primary" style={{ textWrap: 'pretty' }}>{description}</p>
      </div>
    </div>
  );
};
