import { useCallback } from 'react';
import { ChatHistoryMessage, CoraResponse, queryCoraStream } from '@/services/coraApi';
import { Chat, Message } from '@/store/chatStore.types';
import { generateId, detectTopics } from '@/store/chatStore.utils';
import { friendlyStatusText } from './chatStatusHelpers';
import { emit as emitStreamingText, clear as clearStreamingChannel } from './streamingTextChannel';
import { RECOMMENDATIONS } from '@/components/chat/recommendations';
import type { Recommendation, RecommendationType } from '@/components/chat/RecommendationCard';

/**
 * Detect when the backend answered from an empty KB without web search.
 *
 * The backend sets `metadata.kb_empty` when the KB route retrieved zero
 * documents and web search was disabled. In that case the model returns an
 * empty or non-answer fallback, so we replace it with a friendly, actionable
 * message.
 */
function getEmptyKbAnswerText(response: CoraResponse): string | null {
  if (response.metadata?.kb_empty !== true) return null;

  return (
    "I couldn't find anything in the knowledge base that answers this, and web search is currently disabled.\n\n" +
    "Try one of these:\n" +
    "- **Rephrase your question** so it matches the documents in the knowledge base\n" +
    "- **Add relevant documents** via the Documents page\n" +
    "- **Enable web search** in Settings so I can search the web when the KB doesn't have an answer"
  );
}

/**
 * Score a recommendation's relevance to the user's message.
 * Uses word-boundary matching so "carbon" does not match "hydrocarbon".
 * Multi-word phrases are checked via substring inclusion (phrases have implicit boundaries).
 */
function isErrorFallbackResponse(response: CoraResponse): boolean {
  return Array.isArray(response.sources) && response.sources.includes('error_fallback');
}

function scoreRelevance(rec: Recommendation, message: string): number {
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
 */
function getUnseenRecommendations(
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

interface UseBotResponseParams {
  setTypingChatIds: React.Dispatch<React.SetStateAction<Set<string>>>;
  getCurrentChat: (chatId: string) => Chat | null;
  updateChat: (chatId: string, updates: Partial<Chat>) => void;
  activeRequestControllers: React.MutableRefObject<Map<string, AbortController>>;
  pendingBotMessageIds: React.MutableRefObject<Map<string, string>>;
}

export function useBotResponse({
  setTypingChatIds,
  getCurrentChat,
  updateChat,
  activeRequestControllers,
  pendingBotMessageIds,
}: UseBotResponseParams) {
  const getBotResponse = useCallback(async (
    chatId: string,
    userMessageId: string,
    placeholderId: string
  ) => {
    setTypingChatIds(prev => new Set(prev).add(chatId));

    const controller = new AbortController();
    activeRequestControllers.current.set(chatId, controller);
    pendingBotMessageIds.current.set(chatId, placeholderId);

    try {
      const chat = getCurrentChat(chatId);
      if (!chat) return;

      const lastUserMessage = chat.messages.find(m => m.id === userMessageId);
      if (!lastUserMessage) return;

      const detectedTopics = detectTopics(lastUserMessage.content);
      const { topics: unseenTopics, recommendationIds: unseenIds } = getUnseenRecommendations(detectedTopics, chat.shownRecommendations, lastUserMessage.content);

      const messageHistory: ChatHistoryMessage[] = chat.messages
        // Exclude pending messages and the current user message being sent
        .filter(msg => msg.status !== 'pending' && msg.id !== userMessageId)
        .map(msg => ({
          role: msg.sender === 'user' ? ('user' as const) : ('assistant' as const),
          content: msg.content,
        }));

      if (import.meta.env.DEV) {
        console.log('[ChatContext] Building message history:', {
          totalMessages: chat.messages.length,
          nonPendingMessages: chat.messages.filter(msg => msg.status !== 'pending').length,
          historyLength: messageHistory.length,
          historyPreview: messageHistory.slice(-2),
        });
      }

      const requestConversationId = chat.backendConversationId ?? chat.id;
      let streamedResponse: CoraResponse | null = null;
      let streamedText = '';
      let streamingStarted = false;

      const response = await queryCoraStream(
        lastUserMessage.content,
        requestConversationId,
        messageHistory,
        chat.historySignature,
        {
          onStatus: (event) => {
            const { status, message } = event;
            if (import.meta.env.DEV) {
              console.log('[ChatContext] SSE status:', status, message, event.stage, event.progress);
            }
            const currentChat = getCurrentChat(chatId);
            if (currentChat) {
              const statusText = friendlyStatusText(message, status);
              const updatedMessages = currentChat.messages.map(m =>
                m.id === placeholderId
                  ? { ...m, content: statusText, status: 'pending' as const }
                  : m
              );
              updateChat(chatId, { messages: updatedMessages });
            }
          },
          onToken: (chunk) => {
            streamedText += chunk;
            if (!streamingStarted) {
              streamingStarted = true;
              const currentChat = getCurrentChat(chatId);
              if (currentChat) {
                const updatedMessages = currentChat.messages.map(m =>
                  m.id === placeholderId
                    ? { ...m, status: 'streaming' as const }
                    : m
                );
                updateChat(chatId, { messages: updatedMessages });
              }
            }
            emitStreamingText(placeholderId, streamedText);
          },
          onReplace: () => {
            streamedText = '';
            emitStreamingText(placeholderId, '');
          },
          onResult: (result: CoraResponse) => {
            streamedResponse = result;
            // Stop token delivery before the store flips to 'complete'.
            // The single, complete store update (with all fields) is performed
            // by the post-await block below to avoid a redundant render + map.
            clearStreamingChannel(placeholderId);
          },
          onError: (errorId, message) => {
            console.error('[ChatContext] SSE error:', errorId, message);
          },
        },
        { signal: controller.signal }
      );

      if (import.meta.env.DEV) {
        console.log('[ChatContext] Cora streaming response received');
      }

      const finalResponse = streamedResponse ?? response;

      // If the backend returned an error fallback, treat the message as an error
      // and do not show recommendations or source badges.
      if (isErrorFallbackResponse(finalResponse)) {
        const latestChat = getCurrentChat(chatId);
        if (latestChat) {
          const errorMessage: Message = {
            id: placeholderId,
            content: finalResponse.text,
            sender: 'bot',
            timestamp: new Date(),
            replyToMessageId: userMessageId,
            status: 'error',
          };
          const updatedMessages = latestChat.messages.map(m =>
            m.id === placeholderId ? errorMessage : m
          );
          updateChat(chatId, { messages: updatedMessages });
        }
        return;
      }

      // Check for history verification warnings
      if (finalResponse.metadata) {
        if (finalResponse.metadata.history_verification_failed) {
          if (import.meta.env.DEV) console.warn('[ChatContext] History verification failed - resetting chat context');
          // Reset verification context so next turn can establish a fresh trusted thread
          const latestChat = getCurrentChat(chatId);
          if (latestChat && (latestChat.historySignature || latestChat.backendConversationId)) {
            updateChat(chatId, {
              historySignature: undefined,
              backendConversationId: undefined,
            });
          }
        }
        if (finalResponse.metadata.history_items_dropped && finalResponse.metadata.history_items_dropped > 0) {
          if (import.meta.env.DEV) console.warn(`[ChatContext] History items dropped: ${finalResponse.metadata.history_items_dropped}`);
          // Could show a toast here to notify user that some context was trimmed
        }
      }

      // Replace empty/non-answer KB responses with a friendly empty state.
      const botContent = getEmptyKbAnswerText(finalResponse) ?? finalResponse.text;

      const botMessage: Message = {
        id: generateId(),
        content: botContent,
        sender: 'bot',
        timestamp: new Date(),
        agentReasoning: finalResponse.agentReasoning,
        citations: finalResponse.citations,
        sources: finalResponse.sources,
        metadata: finalResponse.metadata,
        quiz: finalResponse.quiz,
        suggestedPrompts: finalResponse.suggestedPrompts,
        triggeredRecommendations: unseenTopics.length > 0 ? unseenTopics : undefined,
        triggeredRecommendationIds: unseenIds.length > 0 ? unseenIds : undefined,
        replyToMessageId: userMessageId,
        status: 'complete',
      };

      const latestChat = getCurrentChat(chatId);
      if (latestChat) {
        const updatedMessages = latestChat.messages.map(m =>
          m.id === placeholderId ? botMessage : m
        );
        updateChat(chatId, {
          messages: updatedMessages,
          shownRecommendations: [...latestChat.shownRecommendations, ...unseenIds],
          ...(finalResponse.conversationId ? { backendConversationId: finalResponse.conversationId } : {}),
          ...(finalResponse.historySignature ? { historySignature: finalResponse.historySignature } : {}),
        });
      }
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') {
        if (import.meta.env.DEV) console.log('Request cancelled by user');
        const chat = getCurrentChat(chatId);
        if (chat) {
          const cancelledMessage: Message = {
            id: placeholderId,
            content: 'Request cancelled.',
            sender: 'bot',
            timestamp: new Date(),
            replyToMessageId: userMessageId,
            status: 'error',
          };
          const updatedMessages = chat.messages.map(m =>
            m.id === placeholderId ? cancelledMessage : m
          );
          updateChat(chatId, { messages: updatedMessages });
        }
        return;
      }

      console.error('Error getting bot response:', error);

      const rawErrorMessage = error instanceof Error ? error.message : '';
      const loweredErrorMessage = rawErrorMessage.toLowerCase();

      let userFacingError = "I'm sorry, I encountered an error. Please try again.";
      if (loweredErrorMessage.includes('403') || loweredErrorMessage.includes('security verification')) {
        userFacingError = 'Security verification failed. Please refresh the page and try again.';
      } else if (loweredErrorMessage.includes('504') || loweredErrorMessage.includes('upstream request timeout')) {
        userFacingError = 'This question is taking too long for the server right now (gateway timeout). Please retry in a moment.';
      } else if (loweredErrorMessage.includes('request timeout') || loweredErrorMessage.includes('timed out')) {
        userFacingError = 'The request timed out before a response was ready. Please retry, or try a shorter/more focused question.';
      } else if (loweredErrorMessage.includes('500') || loweredErrorMessage.includes('internal server error')) {
        userFacingError = 'The AI service had an internal error. Please try again in a moment.';
      } else if (loweredErrorMessage.includes('502') || loweredErrorMessage.includes('bad gateway')) {
        userFacingError = 'The AI service is temporarily unavailable (bad gateway). Please try again in a moment.';
      } else if (loweredErrorMessage.includes('503') || loweredErrorMessage.includes('service unavailable')) {
        userFacingError = 'The AI service is temporarily unavailable. Please try again in a moment.';
      } else if (loweredErrorMessage.includes('server error')) {
        userFacingError = 'The AI service encountered an error. Please try again in a moment.';
      }

      const chat = getCurrentChat(chatId);
      if (!chat) {
        if (import.meta.env.DEV) console.log('Chat was deleted during request, skipping error message');
        return;
      }

      const errorMessage: Message = {
        id: placeholderId,
        content: userFacingError,
        sender: 'bot',
        timestamp: new Date(),
        replyToMessageId: userMessageId,
        status: 'error',
      };

      const updatedMessages = chat.messages.map(m =>
        m.id === placeholderId ? errorMessage : m
      );
      updateChat(chatId, { messages: updatedMessages });
    } finally {
      clearStreamingChannel(placeholderId);
      activeRequestControllers.current.delete(chatId);
      pendingBotMessageIds.current.delete(chatId);
      setTypingChatIds(prev => {
        const next = new Set(prev);
        next.delete(chatId);
        return next;
      });
    }
  }, [activeRequestControllers, pendingBotMessageIds, getCurrentChat, setTypingChatIds, updateChat]);

  return { getBotResponse };
}
