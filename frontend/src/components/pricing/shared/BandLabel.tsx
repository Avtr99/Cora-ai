import React from 'react';

const BandLabel: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <h3 className={`font-inter text-body-sm sm:text-body 3xl:text-lg 4xl:text-xl font-semibold text-text-secondary ${className}`}>{children}</h3>
);

export default BandLabel;
