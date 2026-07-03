import React, { useState, ReactNode, useCallback, useEffect, useRef, useMemo } from 'react';
import { useUserContext } from './useUserContext';
import { ChatContext } from './useChatContext';
import type { ChatContextType } from './useChatContext';
import { useChatStore, useActiveChat } from '@/store/chatStore.simple';
import type { Chat } from '@/store/chatStore.types';
import { useChatActions } from './chat/useChatActions';

interface ChatProviderProps {
  children: ReactNode;
}

/**
 * ChatProvider - Simplified using Zustand for state management
 *
 * Changes from old version:
 * - No useState for chats (using Zustand)
 * - No useRef for chatsRef (Zustand's getState() always fresh)
 * - No localStorage useEffects (Zustand persist middleware handles it)
 * - 558 lines shorter!
 */
export function ChatProvider({ children }: ChatProviderProps) {
  // ==========================================
  // STATE - Use Zustand for chats (no more useState!)
  // ==========================================
  const chats = useChatStore((state) => state.chats);
  const activeChat = useActiveChat();
  const { addChat, updateChat, deleteChat: deleteChatFromStore, setActiveChat: setActiveChatId } = useChatStore();

  // UI state (not persisted) - still use useState
  const [typingChatIds, setTypingChatIds] = useState<Set<string>>(new Set());

  // Request management (still need refs for AbortController)
  const activeRequestControllers = useRef<Map<string, AbortController>>(new Map());
  const pendingBotMessageIds = useRef<Map<string, string>>(new Map());

  useEffect(() => {
    const requestControllers = activeRequestControllers.current;
    const pendingMessageIds = pendingBotMessageIds.current;

    return () => {
      requestControllers.forEach((controller) => {
        controller.abort();
      });
      requestControllers.clear();
      pendingMessageIds.clear();
    };
  }, []);

  // Computed property
  const isTyping = activeChat ? typingChatIds.has(activeChat.id) : false;

  // External dependencies
  const { userProfile } = useUserContext();

  // ==========================================
  // HELPER FUNCTIONS
  // ==========================================

  // Get fresh chat state from Zustand (no stale closures!)
  const getCurrentChat = useCallback((chatId: string): Chat | null => {
    return useChatStore.getState().chats.find(c => c.id === chatId) || null;
  }, []);

  const cancelPendingRequest = useCallback((
    chatId: string,
    markCancelled = false,
    removePending = false
  ) => {
    const controller = activeRequestControllers.current.get(chatId);
    if (controller) {
      controller.abort();
      activeRequestControllers.current.delete(chatId);
    }

    const pendingMessageId = pendingBotMessageIds.current.get(chatId);
    if (pendingMessageId) {
      pendingBotMessageIds.current.delete(chatId);

      const chat = getCurrentChat(chatId);
      if (!chat) return;

      if (markCancelled) {
        const updatedMessages = chat.messages.map(m =>
          m.id === pendingMessageId
            ? { ...m, status: 'cancelled' as const, content: 'This request was cancelled when you switched to another chat.' }
            : m
        );
        updateChat(chatId, { messages: updatedMessages });
      } else if (removePending) {
        const updatedMessages = chat.messages.filter(m => m.id !== pendingMessageId);
        updateChat(chatId, { messages: updatedMessages });
      }
    }
  }, [getCurrentChat, updateChat]);

  // ==========================================
  // ACTIONS (extracted hook)
  // ==========================================
  const {
    createNewChat,
    prepareNewChat,
    setActiveChat: handleSetActiveChat,
    sendMessage,
    stopActiveRequest,
    retryLastUserMessage,
    retryErrorMessage,
    clearActiveChat,
    deleteChat: handleDeleteChat,
  } = useChatActions({
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
  });

  // ==========================================
  // CONTEXT VALUE
  // ==========================================

  const value: ChatContextType = useMemo(() => ({
    chats,
    activeChat,
    isTyping,
    createNewChat,
    prepareNewChat,
    setActiveChat: handleSetActiveChat,
    sendMessage,
    stopActiveRequest,
    retryLastUserMessage,
    retryErrorMessage,
    clearActiveChat,
    deleteChat: handleDeleteChat,
  }), [
    chats,
    activeChat,
    isTyping,
    createNewChat,
    prepareNewChat,
    handleSetActiveChat,
    sendMessage,
    stopActiveRequest,
    retryLastUserMessage,
    retryErrorMessage,
    clearActiveChat,
    handleDeleteChat,
  ]);

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}
