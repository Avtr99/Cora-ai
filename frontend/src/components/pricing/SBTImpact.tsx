import React from "react";
import { IconWrapper } from "@/components/icons/IconWrapper";
import { SEMANTIC } from "@/lib/colors";
import PricingIcon from "@/assets/icons/pricing.svg?react";
import TrendingDownIcon from "@/assets/icons/trending-down.svg?react";
import InfoIcon from "@/assets/icons/info.svg?react";

interface SBTImpactProps {
  category?: string;
}

/**
 * SBTImpact component displays information about the Science-Based Targets initiative
 * and its impact on carbon credit markets
 */
const SBTImpact: React.FC<SBTImpactProps> = ({ category = "Agriculture" }) => {
  return (
    <div>
      <div className="mb-5 md:mb-8">
        <h2 className="font-poppins text-base md:text-lg font-semibold leading-[22px] md:leading-[26px] text-text-primary">Impact of SBTi</h2>
        <p className="font-inter text-xs md:text-xs leading-[16px] md:leading-[18px] text-text-secondary mb-3 md:mb-6">Based on the draft Net-Zero Standard v2.0</p>
        <p className="font-inter text-xs md:text-sm leading-[18px] md:leading-[22px] text-text-primary mb-3 md:mb-5">
          {category === "Renewable Energy"
            ? "Renewable energy credits are considered avoidance credits, not removal credits. Companies aligning with SBTi will likely need to secure more removal credits, potentially reducing future demand for Renewable Energy Credits."
            : category === "Household Devices"
              ? "Household Devices projects issue avoidance-based credits. SBTi's draft Net-Zero Standard prioritises removal credits, which could reduce demand for this category."
              : category === "REDD+"
                ? "REDD+ projects primarily generate avoidance credits. As SBTi signals a stronger focus on removals, organisations may reduce future reliance on REDD+ credits."
                : "SBTi's direction in its draft Net-Zero Standard points clearly towards carbon removal credits. Companies aligning with SBTi will likely need to secure more removal credits, potentially boosting demand in this specific market segment."}
        </p>
        {category === "Agriculture" && (
          <div className="flex items-start gap-2 rounded-lg bg-semantic-warning-bg border border-semantic-warning-border px-2.5 md:px-3.5 py-2 md:py-2.5">
            <IconWrapper Icon={InfoIcon} size={14} color={SEMANTIC.warning.icon} aria-hidden={true} className="shrink-0 mt-0.5" />
            <p className="font-inter text-xs md:text-xs leading-[16px] md:leading-[17px] text-semantic-warning-text">
              <span className="font-semibold">Note:</span> This reflects draft guidance, not the final standard yet. Market dynamics may shift as final standards are published.
            </p>
          </div>
        )}
      </div>

      <div className={`grid grid-cols-1 gap-3 md:gap-6 ${category === "REDD+" || category === "Household Devices" || category === "Renewable Energy" ? "" : "md:grid-cols-2"}`}>
        {category !== "REDD+" && category !== "Household Devices" && category !== "Renewable Energy" && (
          <div className="flex h-full flex-col gap-3 md:gap-5 rounded-xl md:rounded-2xl border border-border-ui bg-surface-card p-4 md:p-6 shadow-sm hover:shadow-md transition-shadow duration-200">
            <div className="flex items-start justify-between gap-2">
              <span className="inline-flex items-center justify-center rounded-full bg-semantic-success-bg px-2 md:px-3 py-0.5 md:py-1 font-inter text-2xs md:text-xs font-semibold leading-[14px] md:leading-[15px] text-semantic-success-text tracking-wide">
                Rising
              </span>
              <div className="flex h-9 w-9 md:h-12 md:w-12 items-center justify-center rounded-lg md:rounded-xl bg-semantic-success-iconBg">
                <IconWrapper Icon={PricingIcon} size={18} color={SEMANTIC.success.icon} aria-hidden={true} className="md:!w-6 md:!h-6" />
              </div>
            </div>
            <div className="space-y-2 md:space-y-3">
              <h3 className="font-poppins text-xs md:text-sm font-semibold leading-[18px] md:leading-[20px] text-text-primary">
                Increasing Demand for Carbon removal credits
              </h3>
              <div>
                <p className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-secondary mb-1.5 md:mb-2">
                  These category credits can have likely higher demand in the future:
                </p>
                <ul className="mt-2 md:mt-3 list-disc space-y-1 md:space-y-1.5 pl-4 md:pl-5">
                  {category === "Agriculture" ? (
                    <>
                      <li className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-primary">Soil Carbon Sequestration</li>
                      <li className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-primary">Agroforestry</li>
                    </>
                  ) : (
                    <>
                      <li className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-primary">Afforestation / Reforestation</li>
                      <li className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-primary">Enhanced Forest Management</li>
                    </>
                  )}
                </ul>
              </div>
            </div>
          </div>
        )}

        <div className={`flex h-full flex-col gap-3 md:gap-5 rounded-xl md:rounded-2xl border border-border-ui bg-surface-card p-4 md:p-6 shadow-sm hover:shadow-md transition-shadow duration-200 ${category === "REDD+" || category === "Household Devices" || category === "Renewable Energy" ? "md:col-span-2" : ""}`}>
          <div className="flex items-start justify-between gap-2">
            <span className="inline-flex items-center justify-center rounded-full bg-semantic-warning-bg px-2 md:px-3 py-0.5 md:py-1 font-inter text-2xs md:text-xs font-semibold leading-[14px] md:leading-[15px] text-semantic-warning-text tracking-wide">
              Declining
            </span>
            <div className="flex h-9 w-9 md:h-12 md:w-12 items-center justify-center rounded-lg md:rounded-xl bg-semantic-warning-iconBg">
              <IconWrapper Icon={TrendingDownIcon} size={18} color={SEMANTIC.warning.icon} aria-hidden={true} className="md:!w-6 md:!h-6" />
            </div>
          </div>
          <div className="space-y-2 md:space-y-3">
            <h3 className="font-poppins text-xs md:text-sm font-semibold leading-[18px] md:leading-[20px] text-text-primary">
              Decreasing Demand for carbon avoidance credits
            </h3>
            {category === "Agriculture" ? (
              <div>
                <p className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-secondary mb-1.5 md:mb-2">
                  These category credits can have likely lower demand in the future:
                </p>
                <ul className="mt-2 md:mt-3 list-disc space-y-1 md:space-y-1.5 pl-4 md:pl-5">
                  <li className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-primary">Optimized Fertilizer Use</li>
                  <li className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-primary">Improved Livestock Management</li>
                  <li className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-primary">Manure Management</li>
                </ul>
              </div>
            ) : category === "Renewable Energy" ? (
              <p className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-secondary">
                These credits are considered avoidance-based and may see lower future demand. They can still support voluntary offsetting or beyond value chain mitigation (BVCM) when transparently communicated.
              </p>
            ) : category === "Household Devices" ? (
              <p className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-secondary">
                These credits are avoidance-based and can have likely lower demand in the future.
              </p>
            ) : (
              <p className="font-inter text-xs md:text-sm leading-[16px] md:leading-[18px] text-text-secondary">
                These credits are avoidance-based and can have likely lower demand in the future.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default SBTImpact;
