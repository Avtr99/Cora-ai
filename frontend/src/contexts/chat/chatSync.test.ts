import { describe, it, expect, vi, beforeEach } from 'vitest';
import { loadChatList, loadChatMessages } from './chatSync';
import { useChatStore } from '@/store/chatStore.simple';
import { useAuthStore } from '@/store/authStore';
import { ChatsApiError, getChat, listChats } from '@/services/chatsApi';
import type { Chat, Message } from '@/store/chatStore.types';

vi.mock('@/services/chatsApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/chatsApi')>();
  return { ...actual, getChat: vi.fn(), listChats: vi.fn() };
});

const mockGetChat = vi.mocked(getChat);
const mockListChats = vi.mocked(listChats);

const serverSummaryChat = (id: string): Chat => ({
  id,
  title: `Chat ${id}`,
  messages: [],
  updatedAt: new Date('2024-01-01'),
  shownRecommendations: [],
  messagesLoaded: false,
});

const loadedChat = (id: string): Chat => {
  const user: Message = {
    id: 'm1',
    content: 'Hello',
    sender: 'user',
    timestamp: new Date('2024-01-02'),
  };
  const bot: Message = {
    id: 'm1-answer',
    content: 'Hi',
    sender: 'bot',
    timestamp: new Date('2024-01-02'),
    replyToMessageId: 'm1',
    status: 'complete',
  };
  return {
    id,
    title: `Chat ${id}`,
    messages: [user, bot],
    updatedAt: new Date('2024-01-02'),
    shownRecommendations: ['project-1'],
    messagesLoaded: true,
  };
};

describe('loadChatList', () => {
  beforeEach(() => {
    useChatStore.setState({ chats: [], activeChatId: null, listStatus: 'idle', loadingChatIds: [] });
    useAuthStore.setState({ status: 'unknown' });
    vi.clearAllMocks();
  });

  it('populates the store and marks the list ready', async () => {
    mockListChats.mockResolvedValueOnce([serverSummaryChat('c1'), serverSummaryChat('c2')]);

    await loadChatList();

    const state = useChatStore.getState();
    expect(state.listStatus).toBe('ready');
    expect(state.chats.map((c) => c.id)).toEqual(['c1', 'c2']);
    expect(state.chats[0].messagesLoaded).toBe(false);
  });

  it('marks the list as error and keeps an empty list on failure', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    mockListChats.mockRejectedValueOnce(new Error('network down'));

    await loadChatList();

    const state = useChatStore.getState();
    expect(state.listStatus).toBe('error');
    expect(state.chats).toEqual([]);
    consoleSpy.mockRestore();
  });

  it('does not refetch once the list has been loaded', async () => {
    useChatStore.setState({ listStatus: 'ready' });

    await loadChatList();

    expect(mockListChats).not.toHaveBeenCalled();
  });
});

describe('loadChatMessages', () => {
  beforeEach(() => {
    useChatStore.setState({ chats: [], activeChatId: null, listStatus: 'ready', loadingChatIds: [] });
    useAuthStore.setState({ status: 'unknown' });
    vi.clearAllMocks();
  });

  it('fills the chat messages and marks it loaded', async () => {
    useChatStore.getState().setChats([serverSummaryChat('c1')]);
    mockGetChat.mockResolvedValueOnce(loadedChat('c1'));

    await loadChatMessages('c1');

    const chat = useChatStore.getState().chats[0];
    expect(mockGetChat).toHaveBeenCalledWith('c1');
    expect(chat.messagesLoaded).toBe(true);
    expect(chat.messages).toHaveLength(2);
    expect(chat.shownRecommendations).toEqual(['project-1']);
    expect(useChatStore.getState().loadingChatIds).toEqual([]);
  });

  it('removes the chat and clears activeChatId on 404', async () => {
    useChatStore.getState().setChats([serverSummaryChat('c1'), serverSummaryChat('c2')]);
    useChatStore.setState({ activeChatId: 'c1' });
    mockGetChat.mockRejectedValueOnce(new ChatsApiError(404));

    await loadChatMessages('c1');

    const state = useChatStore.getState();
    expect(state.chats.map((c) => c.id)).toEqual(['c2']);
    expect(state.activeChatId).toBeNull();
    expect(state.loadingChatIds).toEqual([]);
  });

  it('keeps the chat with empty messages on other errors', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    useChatStore.getState().setChats([serverSummaryChat('c1')]);
    mockGetChat.mockRejectedValueOnce(new Error('network down'));

    await loadChatMessages('c1');

    const chat = useChatStore.getState().chats[0];
    expect(chat).toBeDefined();
    expect(chat.messagesLoaded).toBe(false);
    expect(chat.messages).toEqual([]);
    expect(useChatStore.getState().loadingChatIds).toEqual([]);
    consoleSpy.mockRestore();
  });

  it('skips chats that are already loaded or already loading', async () => {
    useChatStore.getState().setChats([serverSummaryChat('c1')]);
    useChatStore.getState().updateChat('c1', { messagesLoaded: true });

    await loadChatMessages('c1');
    expect(mockGetChat).not.toHaveBeenCalled();

    useChatStore.getState().updateChat('c1', { messagesLoaded: false });
    useChatStore.setState({ loadingChatIds: ['c1'] });

    await loadChatMessages('c1');
    expect(mockGetChat).not.toHaveBeenCalled();
  });
});
