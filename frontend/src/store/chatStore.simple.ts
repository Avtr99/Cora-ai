/**
 * MINIMAL ZUSTAND CHAT STORE
 * 
 * Purpose: Handle ONLY state storage and persistence
 * Actions: Remain in ChatContext.tsx (don't move complex logic)
 * 
 * Benefits of this hybrid approach:
 * 1. Automatic localStorage persistence (no manual useEffect)
 * 2. No useRef needed (Zustand's get() always returns fresh state)
 * 3. Keep actions in familiar Context pattern
 * 4. Gradual migration path
 * 
 * Lines: ~150 (vs 989 in old ChatContext)
 */

import { useMemo } from 'react';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { Chat } from './chatStore.types';
import { validateAndSanitizeChatHistory } from './chatStore.utils';

/**
 * State-only interface
 * No actions here - those stay in ChatContext
 */
interface ChatStoreState {
  chats: Chat[];
  activeChatId: string | null;
}

/**
 * Actions interface
 * Simple CRUD operations only
 */
interface ChatStoreActions {
  // Chat CRUD
  addChat: (chat: Chat) => void;
  updateChat: (chatId: string, updates: Partial<Chat>) => void;
  deleteChat: (chatId: string) => void;
  setActiveChat: (chatId: string | null) => void;
  
  // Bulk operations
  setChats: (chats: Chat[]) => void;
  clearAll: () => void;
}

export type ChatStore = ChatStoreState & ChatStoreActions;

/**
 * Simple Zustand store for chat state
 * 
 * What it does:
 * - Stores chats array and active chat ID
 * - Automatically persists to localStorage
 * - Validates data on load
 * 
 * What it doesn't do:
 * - Complex business logic (stays in ChatContext)
 * - API calls (stays in ChatContext)
 * - Message handling (stays in ChatContext)
 */
export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      // ==========================================
      // STATE
      // ==========================================
      chats: [],
      activeChatId: null,

      // ==========================================
      // SIMPLE CRUD ACTIONS
      // ==========================================

      addChat: (chat: Chat) => {
        set((state) => {
          // Filter out any existing chat with the same ID to prevent duplicates
          const filteredChats = state.chats.filter((c) => c.id !== chat.id);
          return {
            chats: [chat, ...filteredChats],
          };
        });
      },

      updateChat: (chatId: string, updates: Partial<Chat>) => {
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === chatId ? { ...chat, ...updates } : chat
          ),
        }));
      },

      deleteChat: (chatId: string) => {
        set((state) => ({
          chats: state.chats.filter((chat) => chat.id !== chatId),
          activeChatId: state.activeChatId === chatId ? null : state.activeChatId,
        }));
      },

      setActiveChat: (chatId: string | null) => {
        // Allow clearing activeChatId with null
        if (chatId === null) {
          set({ activeChatId: null });
          return;
        }
        
        // Validate that the chatId exists in the store before setting
        const { chats } = get();
        const chatExists = chats.some((chat) => chat.id === chatId);
        
        if (chatExists) {
          set({ activeChatId: chatId });
        } else {
          console.warn(`[ChatStore] Attempted to set active chat to non-existent ID: ${chatId}`);
        }
      },

      setChats: (chats: Chat[]) => {
        set({ chats });
      },

      clearAll: () => {
        set({ chats: [], activeChatId: null });
      },
    }),
    {
      name: 'chat-history',
      storage: createJSONStorage(() => localStorage),
      
      // Only persist chats
      partialize: (state) => ({
        chats: state.chats,
      }),
      
      // Validate on load
      onRehydrateStorage: () => (state) => {
        if (state) {
          try {
            state.chats = validateAndSanitizeChatHistory(state.chats);
            if (import.meta.env.DEV) {
              console.log(`[ChatStore] Loaded ${state.chats.length} chats from localStorage`);
            }
          } catch (error) {
            console.error('[ChatStore] Error validating chats:', error);
            state.chats = [];
          }
        }
      },
    }
  )
);

/**
 * Helper hooks for common patterns
 */

/**
 * Hook to get the currently active chat
 * Uses a single selector to minimize re-renders - only updates when the active chat reference changes
 */
export const useActiveChat = () => {
  return useChatStore((state) => {
    if (!state.activeChatId) return null;
    return state.chats.find((c) => c.id === state.activeChatId) || null;
  });
};

/**
 * Hook to get a chat by its ID
 * Uses memoized selector to prevent unnecessary re-renders when unrelated chats change
 * Zustand's default reference equality ensures we only re-render when the chat object changes
 */
export const useChatById = (chatId: string | null) => {
  // Create a stable selector function that handles null chatId internally
  // Selector only recreates when chatId changes (follows Rules of Hooks - always called)
  const selector = useMemo(
    () => (state: ChatStoreState) => {
      if (!chatId) return null;
      return state.chats.find((c) => c.id === chatId) || null;
    },
    [chatId]
  );

  // Always call useChatStore (follows Rules of Hooks)
  return useChatStore(selector);
};
