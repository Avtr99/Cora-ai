import type { Recommendation, RecommendationType } from './RecommendationCard';
import { caseStudies } from '@/data/caseStudies';

/**
 * Default recommendations for each type
 * Project recommendations are dynamically generated from caseStudies.ts
 * to automatically include new case studies as they are added.
 */
export const RECOMMENDATIONS: Record<RecommendationType, Recommendation[]> = {
  project: caseStudies.map((study) => ({
    id: `project-${study.id}`,
    type: 'project' as const,
    title: study.title,
    description: '', // Not used in new design
    ctaText: '', // Not used in new design
    ctaLink: `/case-study/${study.id}`,
    metadata: {
      type: study.projectType,
      code: study.organizationId
    },
    keywords: study.keywords,
    tagLabel: study.lensLabel,
  })),
  pricing: [
    {
      id: 'pricing-main',
      type: 'pricing',
      title: 'Carbon Credit Pricing by Project Type',
      description: 'Explore historical pricing data and factors influencing VCM prices',
      ctaText: 'View detailed pricing analysis',
      ctaLink: '/pricing',
      metadata: {
        type: 'Market Analysis',
        code: 'All Categories'
      }
    },
    {
      id: 'pricing-1',
      type: 'pricing',
      title: 'Cookstove Carbon Credits Pricing',
      description: '', // Not used in new design
      ctaText: '', // Not used in new design
      ctaLink: '/pricing',
      metadata: {
        type: 'Household Devices',
        code: 'VCS Market'
      }
    },
    {
      id: 'pricing-2',
      type: 'pricing',
      title: 'REDD+ Projects Price Analysis',
      description: '', // Not used in new design
      ctaText: '', // Not used in new design
      ctaLink: '/pricing',
      metadata: {
        type: 'REDD+',
        code: 'VCS Market'
      }
    },
    {
      id: 'pricing-3',
      type: 'pricing',
      title: 'Renewable Energy Credit Pricing',
      description: '', // Not used in new design
      ctaText: '', // Not used in new design
      ctaLink: '/pricing',
      metadata: {
        type: 'Renewable Energy',
        code: 'VCS Market'
      }
    },
    {
      id: 'pricing-4',
      type: 'pricing',
      title: 'Agricultural Carbon Credit Valuations',
      description: '', // Not used in new design
      ctaText: '', // Not used in new design
      ctaLink: '/pricing',
      metadata: {
        type: 'Agriculture',
        code: 'VCS Market'
      }
    }
  ]
};

/**
 * Lookup map for finding recommendations by ID
 * Built from RECOMMENDATIONS for efficient O(1) lookups
 */
export const RECOMMENDATION_BY_ID: Record<string, Recommendation> = (() => {
  const map: Record<string, Recommendation> = {};
  for (const type of Object.keys(RECOMMENDATIONS) as RecommendationType[]) {
    for (const rec of RECOMMENDATIONS[type]) {
      map[rec.id] = rec;
    }
  }
  return map;
})();
