import React from "react";

interface MethodologyExplanationProps {
  category?: string;
}

/**
 * MethodologyExplanation component displays detailed information about
 * specific methodologies for the selected project type
 */
const MethodologyExplanation: React.FC<MethodologyExplanationProps> = ({ category = "Agriculture" }) => {
  // Content for different methodologies
  const methodologyContent = {
    Agriculture: {
      title: "Agriculture",
      description: "Methodologies focus on these project types: Fertilizer - N2O, Grassland/rangeland management, Livestock methane, No-tilllow/till agriculture, Rice cultivation/management, Sustainable agricultural land management",
      methodologies: ["VM0017", "VM0032", "VM0042"]
    },
    "REDD+": {
      title: "REDD+ (Reducing Emissions from Deforestation and Forest Degradation)",
      description: "Methodologies focus on preventing deforestation and forest degradation. Common standards include VCS and Gold Standard, emphasizing the importance of safeguards and community engagement.",
      methodologies: ["VM0006", "VM0007", "VM0009", "VM0015"]
    },
    "Renewable Energy": {
      title: "Renewable Energy",
      description: "Renewable energy carbon offsetting projects aim to reduce greenhouse gas emissions by replacing fossil fuel-based energy sources with renewable alternatives. These projects not only decrease emissions but also promote sustainable energy development.",
      methodologies: ["ACM0002", "ACM0006", "ACM0001"]
    },
    "Household Devices": {
      title: "Household Devices",
      description: "Methodologies focus on Clean cookstove distribution and Water purification device distribution.",
      methodologies: ["AMS II.G", "GS simplified Methodology for Clean and Efficient Cookstoves", "AMS-III.AV"]
    }
  };

  // Get content for the selected category or default to Agriculture
  const content = methodologyContent[category as keyof typeof methodologyContent] || methodologyContent.Agriculture;

  return (
    <div className="bg-surface-card rounded-xl md:rounded-2xl border border-border-ui p-4 md:p-6 h-full flex flex-col shadow-sm">
      <div className="mb-3 md:mb-6">
        <h2 className="font-poppins text-sm md:text-base font-semibold leading-[20px] md:leading-[24px] text-text-primary">
          Methodology explanation
        </h2>
      </div>

      <div className="flex-grow space-y-3 md:space-y-6">
        <div className="space-y-2 md:space-y-3">
          <h3 className="font-poppins text-xs md:text-sm font-semibold leading-[18px] md:leading-[20px] text-text-primary">
            {content.title}
          </h3>
          <p className="font-inter text-xs md:text-sm leading-[18px] md:leading-[20px] text-text-secondary">
            {content.description}
          </p>
        </div>

        <div className="space-y-2 md:space-y-3 pt-1 md:pt-2">
          <h4 className="font-inter text-xs md:text-xs font-semibold leading-[18px] md:leading-[18px] text-text-primary uppercase tracking-wide">
            {category === "Household Devices" || category === "Renewable Energy" ? "Popular methodologies include:" : "Popular VCS methodologies include:"}
          </h4>
          <ul className="space-y-1.5 md:space-y-2">
            {content.methodologies.map((method, index) => (
              <li key={index} className="flex items-center gap-2">
                <div className="h-1 w-1 md:h-1.5 md:w-1.5 rounded-full bg-brand-500 shrink-0"></div>
                <span className="font-inter text-xs md:text-sm leading-[18px] md:leading-[18px] text-text-primary">{method}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};

export default MethodologyExplanation;
