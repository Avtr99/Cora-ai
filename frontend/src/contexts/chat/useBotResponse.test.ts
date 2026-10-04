import { describe, it, expect, vi, beforeEach } from 'vitest';
import { requestBotResponse } from './useBotResponse';
import { useChatStore } from '@/store/chatStore.simple';
import { useAuthStore } from '@/store/authStore';
import { queryCoraStream } from '@/services/coraApi';
import type { CoraResponse } from '@/services/coraApi';
import type { Chat, Message } from '@/store/chatStore.types';

vi.mock('@/services/coraApi', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/coraApi')>();
  return { ...actual, queryCoraStream: vi.fn() };
});

const mockStream = vi.mocked(queryCoraStream);

const userMessage: Message = {
  id: 'm1',
  content: 'What is VM0048?',
  sender: 'user',
  timestamp: new Date('2024-01-01'),
};

const placeholder: Message = {
  id: 'm1-pending',
  content: 'Analyzing request...',
  sender: 'bot',
  timestamp: new Date('2024-01-01'),
  replyToMessageId: 'm1',
  status: 'pending',
};

const seedChat = (overrides: Partial<Chat> = {}): Chat => ({
  id: 'chat-1',
  title: 'Test Chat',
  messages: [userMessage, placeholder],
  updatedAt: new Date('2024-01-01'),
  shownRecommendations: [],
  messagesLoaded: true,
  ...overrides,
});

const getCurrentChat = (chatId: string) =>
  useChatStore.getState().chats.find((c) => c.id === chatId) ?? null;

const updateChat = (chatId: string, updates: Partial<Chat>) =>
  useChatStore.getState().updateChat(chatId, updates);

const runRequest = (chatId = 'chat-1', userMessageId = 'm1', placeholderId = 'm1-pending') =>
  requestBotResponse(chatId, userMessageId, placeholderId, {
    getCurrentChat,
    updateChat,
    signal: new AbortController().signal,
  });

const coraResult = (overrides: Partial<CoraResponse> = {}): CoraResponse => ({
  text: 'VM0048 is a Verra methodology.',
  conversationId: 'chat-1',
  messageId: 'm1',
  answerId: 'm1-answer',
  sources: ['knowledge_base'],
  ...overrides,
});

describe('requestBotResponse', () => {
  beforeEach(() => {
    useChatStore.setState({ chats: [], activeChatId: null, listStatus: 'idle', loadingChatIds: [] });
    useAuthStore.setState({ status: 'unknown' });
    mockStream.mockReset();
  });

  it('sends chat.id as conversation_id and the user message id as message_id', async () => {
    useChatStore.getState().setChats([seedChat()]);
    mockStream.mockResolvedValueOnce(coraResult());

    await runRequest();

    expect(mockStream).toHaveBeenCalledWith(
      'What is VM0048?',
      'chat-1',
      'm1',
      expect.any(Object),
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    );
  });

  it('replaces the placeholder with a bot message whose id is the server answerId', async () => {
    useChatStore.getState().setChats([seedChat()]);
    mockStream.mockResolvedValueOnce(coraResult());

    await runRequest();

    const chat = getCurrentChat('chat-1');
    const bot = chat?.messages.find((m) => m.sender === 'bot');
    expect(chat?.messages.some((m) => m.id === 'm1-pending')).toBe(false);
    expect(bot?.id).toBe('m1-answer');
    expect(bot?.status).toBe('complete');
    expect(bot?.replyToMessageId).toBe('m1');
    expect(bot?.content).toBe('VM0048 is a Verra methodology.');
  });

  it('resends the same user message id on retry', async () => {
    useChatStore.getState().setChats([seedChat()]);
    mockStream.mockResolvedValue(coraResult());

    // First attempt fails server-side, retry reuses the same user message ID (A9)
    await runRequest();
    await runRequest();

    expect(mockStream).toHaveBeenCalledTimes(2);
    expect(mockStream.mock.calls[0][2]).toBe('m1');
    expect(mockStream.mock.calls[1][2]).toBe('m1');
  });

  it('moves the chat to the top and bumps updatedAt after a success', async () => {
    const older = seedChat({ id: 'chat-1' });
    const newer = seedChat({ id: 'chat-2', title: 'Other' });
    useChatStore.setState({ chats: [older, newer] });
    mockStream.mockResolvedValueOnce(coraResult());

    await runRequest('chat-1');

    const chats = useChatStore.getState().chats;
    expect(chats[0].id).toBe('chat-1');
    expect(chats[0].updatedAt.getTime()).toBeGreaterThan(new Date('2024-01-01').getTime());
  });

  it('marks the placeholder as an error message on error_fallback', async () => {
    useChatStore.getState().setChats([seedChat()]);
    mockStream.mockResolvedValueOnce(coraResult({ sources: ['error_fallback'], text: 'Could not answer' }));

    await runRequest();

    const bot = getCurrentChat('chat-1')?.messages.find((m) => m.sender === 'bot');
    expect(bot?.status).toBe('error');
    expect(bot?.content).toBe('Could not answer');
  });
});
