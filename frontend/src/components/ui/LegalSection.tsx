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
      <h2 className="font-poppins text-base md:text-lg 3xl:text-xl 4xl:text-2xl font-semibold leading-6 md:leading-7 3xl:leading-8 text-text-primary mb-3 md:mb-4 3xl:mb-5 4xl:mb-6">
        {heading}
      </h2>
      <div className="font-inter text-sm md:text-base 3xl:text-lg 4xl:text-xl leading-6 md:leading-7 3xl:leading-8 4xl:leading-9 text-text-secondary space-y-3 md:space-y-4 3xl:space-y-5 4xl:space-y-6">
        {children}
      </div>
    </section>
  );
};

export default LegalSection;
