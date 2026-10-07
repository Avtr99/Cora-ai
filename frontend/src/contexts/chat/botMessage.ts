import type { CoraResponse } from '@/services/cora/types';
import type { Message } from '@/store/chatStore.types';
import type { RecommendationType } from '@/components/chat/RecommendationCard';
import { generateId } from '@/store/chatStore.utils';

/**
 * Detect when the backend answered from an empty KB without web search.
 *
 * The backend sets `metadata.kb_empty` when the KB route retrieved zero
 * documents and web search was disabled. In that case the model returns an
 * empty or non-answer fallback, so we replace it with a friendly, actionable
 * message.
 */
export function getEmptyKbAnswerText(response: CoraResponse): string | null {
  if (response.metadata?.kb_empty !== true) return null;

  return (
    "I couldn't find anything in the knowledge base that answers this, and web search is currently disabled.\n\n" +
    "Try one of these:\n" +
    "- **Rephrase your question** so it matches the documents in the knowledge base\n" +
    "- **Add relevant documents** via the Documents page\n" +
    "- **Enable web search** in Settings so I can search the web when the KB doesn't have an answer"
  );
}

export interface BotMessageOptions {
  triggeredTopics?: RecommendationType[];
  triggeredRecommendationIds?: string[];
  timestamp?: Date;
}

/**
 * Build the completed bot `Message` for a successful response.
 *
 * Shared by the live query path (useBotResponse) and the server-chat loader
 * (chatsApi). The message ID is the server's `answerId` so a chat loads
 * identically on every device; `generateId()` is only a fallback for a
 * malformed response.
 */
export function buildBotMessage(
  response: CoraResponse,
  userMessageId: string,
  options: BotMessageOptions = {}
): Message {
  const { triggeredTopics = [], triggeredRecommendationIds = [], timestamp } = options;

  return {
    id: response.answerId || generateId(),
    content: getEmptyKbAnswerText(response) ?? response.text,
    sender: 'bot',
    timestamp: timestamp ?? new Date(),
    agentReasoning: response.agentReasoning,
    citations: response.citations,
    sources: response.sources,
    metadata: response.metadata,
    quiz: response.quiz,
    suggestedPrompts: response.suggestedPrompts,
    triggeredRecommendations: triggeredTopics.length > 0 ? triggeredTopics : undefined,
    triggeredRecommendationIds:
      triggeredRecommendationIds.length > 0 ? triggeredRecommendationIds : undefined,
    replyToMessageId: userMessageId,
    status: 'complete',
  };
}
