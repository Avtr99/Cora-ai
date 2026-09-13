import React from 'react';
import { IconWrapper } from '@/components/icons/IconWrapper';
import { BRAND } from '@/lib/colors';

const InsightRow: React.FC<{
  Icon: React.FC<React.SVGProps<SVGSVGElement>>;
  title: string;
  children: React.ReactNode;
}> = ({ Icon, title, children }) => (
  <div className="flex items-start gap-3">
    <span className="flex h-9 w-9 3xl:h-10 3xl:w-10 4xl:h-12 4xl:w-12 shrink-0 items-center justify-center rounded-lg bg-brand-100">
      <IconWrapper
        Icon={Icon}
        size={18}
        color={BRAND.primary700}
        aria-hidden={true}
        className="[&>svg]:shrink-0 3xl:[&>svg]:h-5 3xl:[&>svg]:w-5 4xl:[&>svg]:h-6 4xl:[&>svg]:w-6"
      />
    </span>
    <div className="min-w-0">
      <h4 className="font-poppins text-sm 3xl:text-base 4xl:text-lg font-semibold text-text-primary">{title}</h4>
      <p className="mt-1 font-inter text-body-sm sm:text-body 3xl:text-lg 4xl:text-xl leading-6 text-text-secondary">{children}</p>
    </div>
  </div>
);

export default InsightRow;
