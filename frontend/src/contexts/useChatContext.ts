import { createContext, useContext } from 'react';
import type { Chat, Message, AgentReasoningStep } from '@/store/chatStore.types';

export interface ChatContextType {
  chats: Chat[];
  activeChat: Chat | null;
  isTyping: boolean;
  /**
   * Creates a new chat with an optional initial message.
   * @param initialMessage - Optional first message to send in the new chat
   * @returns The created Chat object, or null if userProfile is not yet loaded.
   *          Callers must handle null by checking the return value or ensuring
   *          userProfile is ready before calling (e.g., via isReady state).
   */
  createNewChat: (initialMessage?: string) => Chat | null;
  /**
   * Initializes UI state for composing a new chat.
   */
  prepareNewChat: () => void;
  /**
   * Switches the active chat.
   * @param chatId - The ID of the chat to activate.
   */
  setActiveChat: (chatId: string) => void;
  /**
   * Dispatches a user message.
   * @param content - The user message content to send.
   */
  sendMessage: (content: string) => void;
  /**
   * Aborts an in-flight request.
   */
  stopActiveRequest: () => void;
  /**
   * Re-sends the last user message.
   */
  retryLastUserMessage: () => Promise<void>;
  /**
   * Re-attempts a failed message by ID.
   * @param errorMessageId - The ID of the failed message to retry.
   * @returns A promise that resolves when the retry is complete.
   */
  retryErrorMessage: (errorMessageId: string) => Promise<void>;
  /**
   * Clears the currently active chat.
   */
  clearActiveChat: () => void;
  /**
   * Deletes a chat by ID.
   * @param chatId - The ID of the chat to delete.
   */
  deleteChat: (chatId: string) => void;
}

export const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const useChatContext = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error('useChatContext must be used within a ChatProvider');
  }
  return context;
};

// Re-export types for backward compatibility
export type { Chat, Message, AgentReasoningStep };
