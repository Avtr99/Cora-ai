import { useCallback } from 'react';
import { CoraApiError, CoraResponse, CoraStreamError, queryCoraStream } from '@/services/coraApi';
import { Chat, Message } from '@/store/chatStore.types';
import { useChatStore } from '@/store/chatStore.simple';
import { detectTopics } from '@/store/chatStore.utils';
import { friendlyStatusText } from './chatStatusHelpers';
import { buildBotMessage } from './botMessage';
import { getUnseenRecommendations } from '@/components/chat/recommendationSelection';

export interface BotRequestDeps {
  getCurrentChat: (chatId: string) => Chat | null;
  updateChat: (chatId: string, updates: Partial<Chat>) => void;
  signal: AbortSignal;
}

/**
 * Run one user/bot exchange against the backend and fold the result into the
 * chat store.
 *
 * The request sends `chat.id` as `conversation_id` and `userMessageId` as
 * `message_id`: the server loads the chat's stored history itself,
 * and retries resend the same `message_id` so the stored turn is upserted.
 * The finished bot message takes the server's `answerId` via buildBotMessage.
 */
export async function requestBotResponse(
  chatId: string,
  userMessageId: string,
  placeholderId: string,
  { getCurrentChat, updateChat, signal }: BotRequestDeps
): Promise<void> {
  const showError = (content: string, agentReasoning?: Message['agentReasoning']) => {
    const chat = getCurrentChat(chatId);
    if (!chat) return;

    const errorMessage: Message = {
      id: placeholderId,
      content,
      sender: 'bot',
      timestamp: new Date(),
      replyToMessageId: userMessageId,
      status: 'error',
      agentReasoning,
    };
    updateChat(chatId, {
      messages: chat.messages.map(m => m.id === placeholderId ? errorMessage : m),
    });
  };

  try {
    const chat = getCurrentChat(chatId);
    if (!chat) return;

    const lastUserMessage = chat.messages.find(m => m.id === userMessageId);
    if (!lastUserMessage) return;

    const detectedTopics = detectTopics(lastUserMessage.content);
    const { topics: unseenTopics, recommendationIds: unseenIds } = getUnseenRecommendations(detectedTopics, chat.shownRecommendations, lastUserMessage.content);

    let streamedResponse: CoraResponse | null = null;

    // Status-based progress: show pipeline stage updates (searching,
    // retrieving, generating, verifying) in the pending bubble. The
    // complete answer is rendered only when `result` arrives — never
    // intermediate tokens that the orchestrator might discard (KB → web
    // fallback, relevance-check replacement, etc.).
    const response = await queryCoraStream(
      lastUserMessage.content,
      chat.id,
      userMessageId,
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
        onResult: (result: CoraResponse) => {
          streamedResponse = result;
        },
        onError: (errorId, message) => {
          console.error('[ChatContext] SSE error:', errorId, message);
        },
      },
      { signal }
    );

    const finalResponse = streamedResponse ?? response;

    // If the backend returned an error fallback, treat the message as an error
    // and do not show recommendations or source badges.
    if (finalResponse.errorFallback) {
      showError(finalResponse.text, finalResponse.agentReasoning);
      return;
    }

    const botMessage = buildBotMessage(finalResponse, userMessageId, {
      triggeredTopics: unseenTopics,
      triggeredRecommendationIds: unseenIds,
    });

    const latestChat = getCurrentChat(chatId);
    if (latestChat) {
      const updatedMessages = latestChat.messages.map(m =>
        m.id === placeholderId ? botMessage : m
      );
      // Success: bump updatedAt and move the chat to the top of the list.
      useChatStore.getState().touchChat(chatId, {
        messages: updatedMessages,
        shownRecommendations: [...latestChat.shownRecommendations, ...unseenIds],
      });
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      if (import.meta.env.DEV) console.log('Request cancelled by user');
      showError('Request cancelled.');
      return;
    }

    console.error('Error getting bot response:', error);

    // CoraStreamError carries a backend-authored message that is already
    // safe to show verbatim (e.g. security blocks, "service initializing").
    // CoraApiError carries a typed status/kind — map it to copy instead of
    // pattern-matching on message text. Unknown errors get the generic text.
    let userFacingError = "I'm sorry, I encountered an error. Please try again.";
    if (error instanceof CoraStreamError) {
      userFacingError = error.message;
    } else if (error instanceof CoraApiError) {
      if (error.kind === 'timeout') {
        userFacingError = 'The request timed out before a response was ready. Please retry, or try a shorter/more focused question.';
      } else {
        switch (error.status) {
          case 403:
            userFacingError = 'Security verification failed. Please refresh the page and try again.';
            break;
          case 500:
            userFacingError = 'The AI service had an internal error. Please try again in a moment.';
            break;
          case 502:
            userFacingError = 'The AI service is temporarily unavailable (bad gateway). Please try again in a moment.';
            break;
          case 503:
            userFacingError = 'The AI service is temporarily unavailable. Please try again in a moment.';
            break;
          case 504:
            userFacingError = 'This question is taking too long for the server right now (gateway timeout). Please retry in a moment.';
            break;
        }
      }
    }

    showError(
      userFacingError,
      error instanceof CoraStreamError ? error.reasoningSteps : undefined,
    );
  }
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
      await requestBotResponse(chatId, userMessageId, placeholderId, {
        getCurrentChat,
        updateChat,
        signal: controller.signal,
      });
    } finally {
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
