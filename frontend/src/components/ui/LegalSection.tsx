import React from 'react';

interface LegalSectionProps {
  title: string;
  number?: number;
  children: React.ReactNode;
}

/**
 * A numbered section within a legal/policy page.
 * Renders a heading with an optional number prefix and the section content.
 */
const LegalSection: React.FC<LegalSectionProps> = ({ title, number, children }) => {
  const heading = number !== undefined ? `${number}. ${title}` : title;

  return (
    <section>
      <h2 className="font-poppins text-base md:text-lg font-semibold leading-[22px] md:leading-[26px] text-text-primary mb-3 md:mb-4">
        {heading}
      </h2>
      <div className="font-inter text-sm md:text-base leading-[22px] md:leading-[26px] text-text-secondary space-y-3 md:space-y-4">
        {children}
      </div>
    </section>
  );
};

export default LegalSection;
