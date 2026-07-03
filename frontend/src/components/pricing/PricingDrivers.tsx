import React from "react";
import { IconWrapper } from "@/components/icons/IconWrapper";
import { getCategoryTheme } from "@/lib/colors";
import CalendarIcon from "@/assets/icons/calender.svg?react";
import LocationIcon from "@/assets/icons/location.svg?react";
import BookIcon from "@/assets/icons/book.svg?react";
import TreeIcon from "@/assets/icons/tree.svg?react";

interface PricingDriversProps {
  category?: string;
}

/**
 * PricingDrivers component displays the key factors influencing voluntary carbon markets
 * Shows cards for vintage year, project location, certifications, and co-benefits
 */
const PricingDrivers: React.FC<PricingDriversProps> = ({ category = "Agriculture" }) => {
  // Use centralized category themes from colors.ts
  const { iconColor, iconBgColor, textColor } = getCategoryTheme(category);
  const drivers = [
    {
      icon: CalendarIcon,
      title: "Vintage Year",
      description: "Newer vintages tend to trade at a premium",
    },
    {
      icon: LocationIcon,
      title: "Project location",
      description: "Regional policies, local environmental conditions, and proximity to buyers affect pricing",
    },
    {
      icon: BookIcon,
      title: "Certifications and Labels",
      description: "Projects eligible for CORSIA and CCB approved methodology fetch a premium",
    },
    {
      icon: TreeIcon,
      title: "Co-Benefits",
      description: "Projects offering higher co-benefits, such as biodiversity conservation or community development tend to be in more demand",
    },
  ] as const;

  return (
    <div>
      <div className="mb-3 md:mb-6">
        <h2 className="font-poppins text-lg md:text-xl font-semibold leading-[26px] md:leading-[28px] text-text-primary">Pricing Drivers</h2>
        <p className="font-inter text-sm md:text-base leading-[22px] md:leading-[24px] text-text-secondary mb-3 md:mb-6">
          Understand the factors influencing voluntary carbon markets
        </p>
      </div>

      <div>
        <h3 className="font-inter text-xs md:text-sm font-semibold leading-[16px] md:leading-[18px] text-text-primary uppercase tracking-wide mb-2 md:mb-3">Key Influencers</h3>
        
        <div className="grid grid-cols-2 gap-2 md:gap-4 md:grid-cols-2 lg:grid-cols-4">
          {drivers.map((driver, index) => (
            <div 
              key={index} 
              className="flex flex-col gap-2 md:gap-4 rounded-xl md:rounded-2xl border border-border-ui bg-surface-card px-3 md:px-5 pt-3 md:pt-5 pb-4 md:pb-6 min-h-[140px] md:min-h-[200px] shadow-sm hover:shadow-md transition-shadow duration-200"
            >
              <div className="flex items-center justify-center rounded-lg md:rounded-xl p-1.5 md:p-2 w-9 h-9 md:w-12 md:h-12 shrink-0" style={{ backgroundColor: iconBgColor }}>
                <IconWrapper Icon={driver.icon} size={20} color={iconColor} aria-hidden={true} />
              </div>
              <div className="flex flex-col gap-1.5 md:gap-2.5 flex-1">
                <h4 className="font-poppins text-xs md:text-sm font-semibold uppercase leading-[16px] md:leading-[18px] tracking-wide" style={{ color: textColor }}>
                  {driver.title}
                </h4>
                <p className="font-inter text-xs md:text-sm leading-[17px] md:leading-[19px] text-text-secondary">
                  {driver.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default PricingDrivers;
