import React from 'react';
import { Link } from 'react-router-dom';
import { LensBadge } from '@/components/ui/LensBadge';

/**
 * RecommendationType defines the categories of recommendations available in the application
 */
export type RecommendationType = 'project' | 'pricing';

/**
 * Recommendation interface defines the structure of a recommendation
 */
export interface Recommendation {
  id: string;
  type: RecommendationType;
  title: string;
  description: string;
  ctaText: string;
  ctaLink: string;
  iconSrc?: string;
  keywords?: string[];
  /** Dynamic label shown on the recommendation tag badge */
  tagLabel?: string;
  metadata?: {
    type?: string; // e.g., 'Blue Carbon', 'Forestation'
    code?: string; // e.g., 'VCS1764', 'VCS2497'
  };
}

/**
 * Props for the RecommendationCard component
 */
interface RecommendationCardProps {
  recommendation: Recommendation;
}

/**
 * RecommendationCard component displays a recommendation card after chat messages
 * for topics related to projects, methodologies, and pricing
 */
export const RecommendationCard: React.FC<RecommendationCardProps> = ({ recommendation }) => {
  // Default labels by recommendation type. The project tag is the same lens
  // label used on case-study pages, so it renders the shared LensBadge.
  const defaultLabels: Record<RecommendationType, string> = {
    project: 'Understanding high quality credits',
    pricing: 'Market trends'
  };

  const label = recommendation.tagLabel ?? defaultLabels[recommendation.type];

  return (
    <Link to={recommendation.ctaLink} className="block group">
      <div className="flex flex-col items-start gap-4 p-4 bg-surface-card border border-border-ui rounded-xl hover:shadow-sm hover:border-border-ui transition-all duration-200 cursor-pointer">
        {/* Text content */}
        <div className="flex flex-col items-start w-full">
          {/* Project title - with ellipsis for overflow */}
          <h4 className="w-full font-inter font-semibold text-xs leading-4 text-text-primary mb-1 line-clamp-2">
            {recommendation.title}
          </h4>
          
          {/* Project metadata - only show if metadata exists */}
          {recommendation.metadata && (recommendation.metadata.type || recommendation.metadata.code) && (
            <div className="flex flex-row items-baseline gap-1 font-inter font-normal text-xs leading-4 text-text-muted">
              {recommendation.metadata.type && <span>{recommendation.metadata.type}</span>}
              {recommendation.metadata.type && recommendation.metadata.code && <span>•</span>}
              {recommendation.metadata.code && <span>{recommendation.metadata.code}</span>}
            </div>
          )}
        </div>
        
        {/* Tag badge — project uses the shared lens badge; pricing keeps its own market-trend styling */}
        {recommendation.type === 'project' ? (
          <LensBadge label={label} />
        ) : (
          <span className="inline-flex items-center justify-center px-3 py-1 bg-semantic-warning-iconBg rounded-full font-inter text-xs font-medium whitespace-nowrap w-fit text-semantic-warning-text">
            {label}
          </span>
        )}
      </div>
    </Link>
  );
};
