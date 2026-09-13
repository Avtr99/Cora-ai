import React from 'react';
import BandLabel from '@/components/pricing/shared/BandLabel';

const ContextSection: React.FC<{ label: string; className?: string; children: React.ReactNode }> = ({
  label,
  className = '',
  children,
}) => (
  <section className={`mt-10 3xl:mt-14 4xl:mt-16 ${className}`}>
    <BandLabel>{label}</BandLabel>
    <div className="mt-4">{children}</div>
  </section>
);

export default ContextSection;
