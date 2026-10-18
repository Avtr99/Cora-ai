import { RecommendationType } from '@/components/chat/RecommendationCard';
import { CASE_STUDY_TOPIC_WORDS, CASE_STUDY_TOPIC_PHRASES } from '@/components/chat/recommendations';

// Module-scoped counter for fallback ID generation to prevent collisions
let fallbackCounter = 0;

/**
 * Generate a unique ID with fallback for SSR and older browsers
 * Uses crypto.randomUUID() when available, otherwise falls back to a combination of
 * timestamp + incrementing counter + random segment for guaranteed uniqueness
 */
export const generateId = (): string => {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for SSR and older browsers with guaranteed uniqueness
  // Format: timestamp-counter-random (e.g., 1697478234567-1-a3f2k9)
  return `${Date.now()}-${++fallbackCounter}-${Math.random().toString(36).substring(2, 9)}`;
};

/**
 * Generate a title based on the first message
 * Take the first 30 characters and add ellipsis if longer
 */
export const generateChatTitle = (message: string): string => {
  if (message.length <= 30) {
    return message;
  }
  return message.substring(0, 30) + '...';
};

/**
 * Detect topics from message content to trigger recommendations
 * Analyzes the message for keywords related to projects, methodologies, and pricing
 */
export const detectTopics = (message: string): RecommendationType[] => {
  const topics: RecommendationType[] = [];
  const lowerMessage = message.toLowerCase();

  // Helper: Check if word exists with word boundaries (avoids "projection" matching "project")
  // Keywords come from caseStudies data, so escape regex metacharacters before interpolating.
  const hasWord = (word: string): boolean => {
    const escaped = word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const regex = new RegExp(`\\b${escaped}\\b`, 'i');
    return regex.test(message);
  };

  // Helper: Check if phrase exists (for multi-word terms)
  const hasPhrase = (phrase: string): boolean => {
    return lowerMessage.includes(phrase);
  };

  // Helper: Check multiple words (any match)
  const hasAnyWord = (words: string[]): boolean => {
    return words.some(word => hasWord(word));
  };

  // Project-related keywords: generic VCM terms + case-study-specific terms
  // derived from caseStudies[*].keywords (no manual sync needed).
  if (
    hasAnyWord(['project', 'projects']) ||
    hasPhrase('case study') ||
    hasPhrase('co-benefit') ||
    hasPhrase('co-benefits') ||
    hasAnyWord(CASE_STUDY_TOPIC_WORDS) ||
    CASE_STUDY_TOPIC_PHRASES.some(phrase => hasPhrase(phrase)) ||
    hasAnyWord(['methodology', 'methodologies', 'protocol', 'protocols', 'validation', 'verification']) ||
    hasAnyWord(['standard', 'standards']) ||
    hasPhrase('vm0048') ||
    hasPhrase('vm 0048') ||
    hasPhrase('carbon accounting')
  ) {
    topics.push('project');
  }

  // Pricing-related keywords - requires context to avoid false positives
  const hasPricingKeyword = 
    hasAnyWord(['price', 'prices', 'pricing', 'cost', 'costs']) ||
    hasAnyWord(['dollar', 'dollars', 'expensive', 'cheap']) ||
    lowerMessage.includes('$');

  const hasCarbonContext =
    hasAnyWord(['carbon', 'credit', 'credits', 'offset', 'offsets', 'emission', 'emissions']) ||
    hasAnyWord(['vcm', 'market', 'markets']);

  // Explicit pricing phrases that don't need additional context
  const hasExplicitPricingPhrase =
    hasPhrase('price per ton') ||
    hasPhrase('price per tonne') ||
    hasPhrase('cost per ton') ||
    hasPhrase('cost per tonne') ||
    hasPhrase('$/t') ||
    hasPhrase('dollar per ton') ||
    hasPhrase('carbon price') ||
    hasPhrase('carbon pricing') ||
    hasPhrase('credit price') ||
    hasPhrase('offset price');

  if (hasExplicitPricingPhrase || (hasPricingKeyword && hasCarbonContext)) {
    topics.push('pricing');
  }

  return topics;
};
