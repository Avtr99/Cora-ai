import { useCallback } from 'react';
import { sanitizeInput } from '@/lib/security';
import { Chat, Message } from '@/store/chatStore.types';
import { generateChatTitle, generateId } from '@/store/chatStore.utils';
import { useBotResponse } from './useBotResponse';

interface UseChatActionsParams {
  activeChat: Chat | null;
  userProfile: { id: string } | null;
  setTypingChatIds: React.Dispatch<React.SetStateAction<Set<string>>>;
  getCurrentChat: (chatId: string) => Chat | null;
  cancelPendingRequest: (chatId: string, markCancelled?: boolean, removePending?: boolean) => void;
  addChat: (chat: Chat) => void;
  updateChat: (chatId: string, updates: Partial<Chat>) => void;
  deleteChatFromStore: (chatId: string) => void;
  setActiveChatId: (chatId: string | null) => void;
  activeRequestControllers: React.MutableRefObject<Map<string, AbortController>>;
  pendingBotMessageIds: React.MutableRefObject<Map<string, string>>;
}

export function useChatActions({
  activeChat,
  userProfile,
  setTypingChatIds,
  getCurrentChat,
  cancelPendingRequest,
  addChat,
  updateChat,
  deleteChatFromStore,
  setActiveChatId,
  activeRequestControllers,
  pendingBotMessageIds,
}: UseChatActionsParams) {
  const { getBotResponse } = useBotResponse({
    setTypingChatIds,
    getCurrentChat,
    updateChat,
    activeRequestControllers,
    pendingBotMessageIds,
  });

  /**
   * Creates a new chat session with an optional initial message.
   */
  const createNewChat = useCallback((initialMessage?: string): Chat | null => {
    if (!userProfile) {
      console.warn('[ChatContext] UserContext not ready yet, cannot create chat');
      return null;
    }

    const newChatId = generateId();
    const newChat: Chat = {
      id: newChatId,
      title: initialMessage ? generateChatTitle(initialMessage) : 'New Chat',
      messages: [],
      createdAt: new Date(),
      shownRecommendations: [],
    };

    addChat(newChat);
    setActiveChatId(newChatId);

    if (initialMessage) {
      const sanitizedContent = sanitizeInput(initialMessage);
      const userMessageId = generateId();
      const placeholderId = `${userMessageId}-pending`;

      const userMessage: Message = {
        id: userMessageId,
        content: sanitizedContent,
        sender: 'user',
        timestamp: new Date(),
      };

      const placeholderMessage: Message = {
        id: placeholderId,
        content: 'Analyzing request...',
        sender: 'bot',
        timestamp: new Date(),
        replyToMessageId: userMessageId,
        status: 'pending',
      };

      updateChat(newChatId, {
        messages: [userMessage, placeholderMessage],
      });

      void getBotResponse(newChatId, userMessageId, placeholderId);
    }

    return newChat;
  }, [addChat, setActiveChatId, updateChat, userProfile, getBotResponse]);

  const prepareNewChat = useCallback(() => {
    const newChatId = generateId();
    setActiveChatId(newChatId);
  }, [setActiveChatId]);

  const setActiveChat = useCallback((chatId: string) => {
    const currentActiveId = activeChat?.id;

    if (currentActiveId && currentActiveId !== chatId) {
      cancelPendingRequest(currentActiveId, true);
      setTypingChatIds(prev => {
        const next = new Set(prev);
        next.delete(currentActiveId);
        return next;
      });
    }

    setActiveChatId(chatId);
  }, [activeChat, cancelPendingRequest, setActiveChatId, setTypingChatIds]);

  const clearActiveChat = useCallback(() => {
    const currentActiveId = activeChat?.id;
    if (currentActiveId) {
      cancelPendingRequest(currentActiveId, false, true);
      setTypingChatIds(prev => {
        const next = new Set(prev);
        next.delete(currentActiveId);
        return next;
      });
    }
    setActiveChatId(null);
  }, [activeChat, cancelPendingRequest, setActiveChatId, setTypingChatIds]);

  const stopActiveRequest = useCallback(() => {
    const currentActiveId = activeChat?.id;
    if (!currentActiveId) return;

    cancelPendingRequest(currentActiveId, true, true);
    setTypingChatIds(prev => {
      const next = new Set(prev);
      next.delete(currentActiveId);
      return next;
    });
  }, [activeChat, cancelPendingRequest, setTypingChatIds]);

  const deleteChat = useCallback((chatId: string) => {
    cancelPendingRequest(chatId, false, true);
    activeRequestControllers.current.delete(chatId);
    pendingBotMessageIds.current.delete(chatId);
    setTypingChatIds(prev => {
      const next = new Set(prev);
      next.delete(chatId);
      return next;
    });
    deleteChatFromStore(chatId);
  }, [activeRequestControllers, pendingBotMessageIds, cancelPendingRequest, deleteChatFromStore, setTypingChatIds]);

  /**
   * Sends a message in the active chat or creates a new chat if none is active.
   */
  const sendMessage = useCallback((content: string) => {
    if (!content.trim()) return;

    if (!userProfile) {
      console.warn('[ChatContext] UserContext not ready yet, skipping message');
      return;
    }

    const sanitizedContent = sanitizeInput(content);
    const userMessageId = generateId();

    let targetChatId = activeChat?.id;
    let targetChat: Chat;

    if (!activeChat) {
      targetChatId = generateId();
      targetChat = {
        id: targetChatId,
        title: generateChatTitle(sanitizedContent),
        messages: [],
        createdAt: new Date(),
        shownRecommendations: [],
      };
      addChat(targetChat);
      setActiveChatId(targetChatId);
    } else {
      targetChat = activeChat;
      targetChatId = activeChat.id;
    }

    const userMessage: Message = {
      id: userMessageId,
      content: sanitizedContent,
      sender: 'user',
      timestamp: new Date(),
    };

    const placeholderId = `${userMessageId}-pending`;
    const placeholderMessage: Message = {
      id: placeholderId,
      content: 'Analyzing request...',
      sender: 'bot',
      timestamp: new Date(),
      replyToMessageId: userMessageId,
      status: 'pending',
    };

    const updatedMessages = [...targetChat.messages, userMessage, placeholderMessage];

    updateChat(targetChatId, {
      messages: updatedMessages,
      title: targetChat.messages.length === 0 ? generateChatTitle(sanitizedContent) : targetChat.title,
    });

    void getBotResponse(targetChatId, userMessageId, placeholderId);
  }, [activeChat, userProfile, addChat, updateChat, setActiveChatId, getBotResponse]);

  const retryLastUserMessage = useCallback(async () => {
    if (!activeChat) return;

    const lastUserMessage = [...activeChat.messages].reverse().find(m => m.sender === 'user');
    if (!lastUserMessage) return;

    const placeholderId = `${lastUserMessage.id}-retry-${Date.now()}`;
    const placeholderMessage: Message = {
      id: placeholderId,
      content: 'Analyzing request...',
      sender: 'bot',
      timestamp: new Date(),
      replyToMessageId: lastUserMessage.id,
      status: 'pending',
    };

    updateChat(activeChat.id, {
      messages: [...activeChat.messages, placeholderMessage],
    });

    await getBotResponse(activeChat.id, lastUserMessage.id, placeholderId);
  }, [activeChat, updateChat, getBotResponse]);

  const retryErrorMessage = useCallback(async (errorMessageId: string) => {
    const chat = activeChat;
    if (!chat) return;

    const errMsg = chat.messages.find(m => m.id === errorMessageId && m.sender === 'bot');
    if (!errMsg) return;

    let targetUserId = errMsg.replyToMessageId;
    if (!targetUserId) {
      const errIndex = chat.messages.findIndex(m => m.id === errorMessageId);
      if (errIndex > 0) {
        for (let i = errIndex - 1; i >= 0; i--) {
          if (chat.messages[i].sender === 'user') {
            targetUserId = chat.messages[i].id;
            break;
          }
        }
      }
    }

    if (!targetUserId) return;

    const updatedMessages = chat.messages.map(m =>
      m.id === errorMessageId
        ? { ...m, status: 'pending' as const, content: 'Analyzing request...', timestamp: new Date() }
        : m
    );
    updateChat(chat.id, { messages: updatedMessages });

    await getBotResponse(chat.id, targetUserId, errorMessageId);
  }, [activeChat, updateChat, getBotResponse]);

  return {
    createNewChat,
    prepareNewChat,
    setActiveChat,
    sendMessage,
    stopActiveRequest,
    retryLastUserMessage,
    retryErrorMessage,
    clearActiveChat,
    deleteChat,
  };
}
