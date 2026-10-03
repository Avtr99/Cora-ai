import { describe, it, expect, beforeEach } from 'vitest';
import { useChatStore, removeLegacyChatHistory } from './chatStore.simple';
import { useAuthStore } from './authStore';
import type { Chat } from './chatStore.types';

const createMockChat = (id: string, title: string = `Chat ${id}`): Chat => ({
  id,
  title,
  messages: [],
  updatedAt: new Date('2024-01-01'),
  shownRecommendations: [],
  messagesLoaded: true,
});

describe('useChatStore', () => {
  beforeEach(() => {
    // Reset stores to initial state before each test
    useChatStore.setState({ chats: [], activeChatId: null, listStatus: 'idle', loadingChatIds: [] });
    useAuthStore.setState({ status: 'unknown' });
    localStorage.clear();
  });

  describe('addChat', () => {
    it('adds a chat to the store', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);

      expect(useChatStore.getState().chats).toHaveLength(1);
      expect(useChatStore.getState().chats[0].id).toBe('chat-1');
    });

    it('prevents duplicate chat IDs by replacing existing', () => {
      const chat1 = createMockChat('chat-1', 'Original');
      useChatStore.getState().addChat(chat1);

      const chat2 = createMockChat('chat-1', 'Updated');
      useChatStore.getState().addChat(chat2);

      expect(useChatStore.getState().chats).toHaveLength(1);
      expect(useChatStore.getState().chats[0].title).toBe('Updated');
    });

    it('prepends new chat to the beginning of the array', () => {
      const chat1 = createMockChat('chat-1');
      const chat2 = createMockChat('chat-2');

      useChatStore.getState().addChat(chat1);
      useChatStore.getState().addChat(chat2);

      expect(useChatStore.getState().chats[0].id).toBe('chat-2');
      expect(useChatStore.getState().chats[1].id).toBe('chat-1');
    });
  });

  describe('updateChat', () => {
    it('updates a chat by ID', () => {
      const chat = createMockChat('chat-1', 'Original');
      useChatStore.getState().addChat(chat);

      useChatStore.getState().updateChat('chat-1', { title: 'Updated' });

      expect(useChatStore.getState().chats[0].title).toBe('Updated');
    });

    it('does not modify other chats', () => {
      const chat1 = createMockChat('chat-1', 'First');
      const chat2 = createMockChat('chat-2', 'Second');
      useChatStore.getState().addChat(chat1);
      useChatStore.getState().addChat(chat2);

      useChatStore.getState().updateChat('chat-1', { title: 'Updated First' });

      expect(useChatStore.getState().chats.find(c => c.id === 'chat-2')?.title).toBe('Second');
    });

    it('handles non-existent chat ID gracefully', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);

      useChatStore.getState().updateChat('non-existent', { title: 'Updated' });

      expect(useChatStore.getState().chats).toHaveLength(1);
      expect(useChatStore.getState().chats[0].title).toBe('Chat chat-1');
    });
  });

  describe('touchChat', () => {
    it('applies updates, bumps updatedAt, and moves the chat to the top', () => {
      const chat1 = createMockChat('chat-1');
      const chat2 = createMockChat('chat-2');
      useChatStore.setState({ chats: [chat1, chat2] });

      useChatStore.getState().touchChat('chat-2', { title: 'New Title' });

      const state = useChatStore.getState();
      expect(state.chats[0].id).toBe('chat-2');
      expect(state.chats[0].title).toBe('New Title');
      expect(state.chats[0].updatedAt.getTime()).toBeGreaterThan(chat2.updatedAt.getTime());
      expect(state.chats[1].id).toBe('chat-1');
    });

    it('does nothing for an unknown chat', () => {
      const chat1 = createMockChat('chat-1');
      useChatStore.setState({ chats: [chat1] });

      useChatStore.getState().touchChat('missing', { title: 'X' });

      expect(useChatStore.getState().chats[0].id).toBe('chat-1');
    });
  });

  describe('deleteChat', () => {
    it('removes a chat by ID', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);

      useChatStore.getState().deleteChat('chat-1');

      expect(useChatStore.getState().chats).toHaveLength(0);
    });

    it('clears activeChatId if the deleted chat was active', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);
      useChatStore.getState().setActiveChat('chat-1');

      useChatStore.getState().deleteChat('chat-1');

      expect(useChatStore.getState().activeChatId).toBeNull();
    });

    it('preserves activeChatId if a different chat was active', () => {
      const chat1 = createMockChat('chat-1');
      const chat2 = createMockChat('chat-2');
      useChatStore.getState().addChat(chat1);
      useChatStore.getState().addChat(chat2);
      useChatStore.getState().setActiveChat('chat-2');

      useChatStore.getState().deleteChat('chat-1');

      expect(useChatStore.getState().activeChatId).toBe('chat-2');
    });
  });

  describe('setActiveChat', () => {
    it('sets active chat when chat exists', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);

      useChatStore.getState().setActiveChat('chat-1');

      expect(useChatStore.getState().activeChatId).toBe('chat-1');
    });

    it('allows clearing active chat with null', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);
      useChatStore.getState().setActiveChat('chat-1');

      useChatStore.getState().setActiveChat(null);

      expect(useChatStore.getState().activeChatId).toBeNull();
    });
  });

  describe('setChats', () => {
    it('replaces all chats', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);

      const newChats = [createMockChat('chat-3'), createMockChat('chat-4')];
      useChatStore.getState().setChats(newChats);

      expect(useChatStore.getState().chats).toHaveLength(2);
      expect(useChatStore.getState().chats.map(c => c.id)).toEqual(['chat-3', 'chat-4']);
    });
  });

  describe('clearAll', () => {
    it('resets chats, active chat, listStatus, and loading ids', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);
      useChatStore.getState().setActiveChat('chat-1');
      useChatStore.setState({ listStatus: 'ready', loadingChatIds: ['chat-1'] });

      useChatStore.getState().clearAll();

      const state = useChatStore.getState();
      expect(state.chats).toHaveLength(0);
      expect(state.activeChatId).toBeNull();
      expect(state.listStatus).toBe('idle');
      expect(state.loadingChatIds).toEqual([]);
    });
  });

  describe('loading state', () => {
    it('marks and unmarks a chat as loading', () => {
      useChatStore.getState().markChatLoading('chat-1');
      expect(useChatStore.getState().loadingChatIds).toEqual(['chat-1']);

      // Idempotent while already loading
      useChatStore.getState().markChatLoading('chat-1');
      expect(useChatStore.getState().loadingChatIds).toEqual(['chat-1']);

      useChatStore.getState().unmarkChatLoading('chat-1');
      expect(useChatStore.getState().loadingChatIds).toEqual([]);
    });
  });

  describe('memory-only persistence', () => {
    it('does not write chat data to localStorage', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);
      useChatStore.getState().setActiveChat('chat-1');

      expect(localStorage.getItem('chat-history')).toBeNull();
    });
  });

  describe('sign-out cleanup', () => {
    it('clears the store when auth status becomes required', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);
      useChatStore.getState().setActiveChat('chat-1');
      useChatStore.setState({ listStatus: 'ready' });

      useAuthStore.getState().setStatus('required');

      const state = useChatStore.getState();
      expect(state.chats).toHaveLength(0);
      expect(state.activeChatId).toBeNull();
      expect(state.listStatus).toBe('idle');
    });

    it('keeps the store for other auth transitions', () => {
      const chat = createMockChat('chat-1');
      useChatStore.getState().addChat(chat);

      useAuthStore.getState().setStatus('authenticated');

      expect(useChatStore.getState().chats).toHaveLength(1);
    });
  });
});

describe('useActiveChat', () => {
  beforeEach(() => {
    useChatStore.setState({ chats: [], activeChatId: null });
    useAuthStore.setState({ status: 'unknown' });
  });

  it('returns the active chat object', () => {
    const chat = createMockChat('active-1', 'Active Chat');
    useChatStore.setState({ chats: [chat], activeChatId: 'active-1' });

    const activeChat = useChatStore.getState().chats.find(
      c => c.id === useChatStore.getState().activeChatId
    );
    expect(activeChat).toEqual(chat);
  });

  it('returns null when no active chat', () => {
    useChatStore.setState({ chats: [], activeChatId: null });
    expect(useChatStore.getState().activeChatId).toBeNull();
  });
});

describe('removeLegacyChatHistory', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('removes the old localStorage chat key', () => {
    localStorage.setItem('chat-history', JSON.stringify({ state: { chats: [] } }));

    removeLegacyChatHistory();

    expect(localStorage.getItem('chat-history')).toBeNull();
  });

  it('does not throw when the key is absent', () => {
    expect(() => removeLegacyChatHistory()).not.toThrow();
  });
});
