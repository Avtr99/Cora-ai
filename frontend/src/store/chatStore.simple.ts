/**
 * MINIMAL ZUSTAND CHAT STORE
 *
 * Purpose: Handle ONLY state storage
 * Actions: Remain in ChatContext.tsx (don't move complex logic)
 *
 * Chats are memory-only (Phase 7): the server owns persistence, the browser
 * holds no chat data in localStorage. On sign-out (auth status 'required')
 * the store is cleared, so nothing is left behind.
 */

import { useMemo } from 'react';
import { create } from 'zustand';
import { Chat } from './chatStore.types';
import { useAuthStore } from './authStore';

/** localStorage key used by the pre-Phase-7 persisted chat store (D18). */
const LEGACY_CHAT_HISTORY_KEY = 'chat-history';

export type ChatListStatus = 'idle' | 'loading' | 'ready' | 'error';

/**
 * State-only interface
 * No actions here - those stay in ChatContext
 */
interface ChatStoreState {
  chats: Chat[];
  activeChatId: string | null;
  /** Server chat-list load status: 'idle' until the first load attempt. */
  listStatus: ChatListStatus;
  /** Chat IDs whose messages are being fetched from the server right now. */
  loadingChatIds: string[];
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

  // Server sync state
  setListStatus: (status: ChatListStatus) => void;
  markChatLoading: (chatId: string) => void;
  unmarkChatLoading: (chatId: string) => void;
  /** Apply updates, bump updatedAt to now, and move the chat to the top. */
  touchChat: (chatId: string, updates?: Partial<Chat>) => void;
}

export type ChatStore = ChatStoreState & ChatStoreActions;

/**
 * Simple Zustand store for chat state
 *
 * What it does:
 * - Stores chats array and active chat ID (in memory only)
 * - Tracks server list/detail loading state
 *
 * What it doesn't do:
 * - Complex business logic (stays in ChatContext)
 * - API calls (stays in ChatContext / services)
 * - Message handling (stays in ChatContext)
 */
export const useChatStore = create<ChatStore>()((set, get) => ({
  // ==========================================
  // STATE
  // ==========================================
  chats: [],
  activeChatId: null,
  listStatus: 'idle',
  loadingChatIds: [],

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
      loadingChatIds: state.loadingChatIds.filter((id) => id !== chatId),
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
    set({ chats: [], activeChatId: null, listStatus: 'idle', loadingChatIds: [] });
  },

  // ==========================================
  // SERVER SYNC STATE
  // ==========================================

  setListStatus: (status: ChatListStatus) => {
    set({ listStatus: status });
  },

  markChatLoading: (chatId: string) => {
    set((state) =>
      state.loadingChatIds.includes(chatId)
        ? state
        : { loadingChatIds: [...state.loadingChatIds, chatId] }
    );
  },

  unmarkChatLoading: (chatId: string) => {
    set((state) => ({
      loadingChatIds: state.loadingChatIds.filter((id) => id !== chatId),
    }));
  },

  touchChat: (chatId: string, updates?: Partial<Chat>) => {
    set((state) => {
      const chat = state.chats.find((c) => c.id === chatId);
      if (!chat) return state;
      const updated: Chat = { ...chat, ...updates, updatedAt: new Date() };
      return { chats: [updated, ...state.chats.filter((c) => c.id !== chatId)] };
    });
  },
}));

// Clear all chat state when the session is lost (sign-out or a 401 marked the
// session required). The browser must not keep chats from a previous session.
useAuthStore.subscribe((state, prevState) => {
  if (state.status === 'required' && prevState.status !== 'required') {
    useChatStore.getState().clearAll();
  }
});

/**
 * Remove chat data persisted by the pre-Phase-7 localStorage store (D18).
 * Called once from main.tsx before React renders so an upgrade leaves no
 * chat content in the browser.
 */
export function removeLegacyChatHistory(): void {
  try {
    localStorage.removeItem(LEGACY_CHAT_HISTORY_KEY);
  } catch {
    // localStorage may be unavailable (private browsing) — non-fatal.
  }
}

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
