import { RECOMMENDATIONS } from './recommendations';
import type { Recommendation, RecommendationType } from './RecommendationCard';

/**
 * Score a recommendation's relevance to the user's message.
 * Uses word-boundary matching so "carbon" does not match "hydrocarbon".
 * Multi-word phrases are checked via substring inclusion (phrases have implicit boundaries).
 */
export function scoreRelevance(rec: Recommendation, message: string): number {
  if (!rec.keywords || rec.keywords.length === 0) return 0;
  const lowerMessage = message.toLowerCase();
  let score = 0;
  for (const kw of rec.keywords) {
    const lowerKw = kw.toLowerCase();
    // Multi-word phrases: use substring inclusion (e.g. "assisted natural regeneration")
    if (lowerKw.includes(' ')) {
      if (lowerMessage.includes(lowerKw)) score += 1;
      continue;
    }
    // Single words: require word boundary to avoid partial matches
    const regex = new RegExp(`\\b${lowerKw}\\b`, 'i');
    if (regex.test(message)) {
      score += 1;
    }
  }
  return score;
}

/**
 * Get unseen recommendations based on detected topics, previously shown IDs,
 * and relevance to the user's message.
 * Returns both the topic types and the specific recommendation IDs to track.
 * Cycles through available recommendations to avoid showing the same one twice.
 *
 * The same function drives live turns (useBotResponse) and replay of
 * server-loaded chats (chatsApi), so both paths pick identical cards.
 */
export function getUnseenRecommendations(
  detectedTopics: RecommendationType[],
  shownIds: string[],
  message: string
): {
  topics: RecommendationType[];
  recommendationIds: string[];
} {
  const topics: RecommendationType[] = [];
  const recommendationIds: string[] = [];

  for (const topic of detectedTopics) {
    const recommendations = RECOMMENDATIONS[topic];
    if (!recommendations || recommendations.length === 0) continue;

    // Filter to unseen recommendations
    const unseen = recommendations.filter(rec => !shownIds.includes(rec.id));
    if (unseen.length === 0) continue;

    // Score by keyword relevance and pick the best match
    const scored = unseen.map(rec => ({ rec, score: scoreRelevance(rec, message) }));
    scored.sort((a, b) => b.score - a.score);

    // Pick the highest-scoring unseen recommendation (falls back to first if no keywords match)
    const best = scored[0].rec;
    topics.push(topic);
    recommendationIds.push(best.id);
  }

  return { topics, recommendationIds };
}
