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
    useChatStore.setState({ chats: [seedChat()] });
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
    useChatStore.setState({ chats: [seedChat()] });
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
    useChatStore.setState({ chats: [seedChat()] });
    mockStream.mockResolvedValue(coraResult());

    // First attempt fails server-side, retry reuses the same user message ID
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

  it('keeps the query trace when a result is marked as an error fallback', async () => {
    useChatStore.setState({ chats: [seedChat()] });
    const agentReasoning = [{ agentName: 'Search the web', nodeName: 'Web Search' }];
    mockStream.mockResolvedValueOnce(coraResult({ errorFallback: true, text: 'Could not answer', agentReasoning }));

    await runRequest();

    const bot = getCurrentChat('chat-1')?.messages.find((m) => m.sender === 'bot');
    expect(bot?.status).toBe('error');
    expect(bot?.content).toBe('Could not answer');
    expect(bot?.agentReasoning).toEqual(agentReasoning);
  });

  it('shows the backend message and partial reasoning on CoraStreamError', async () => {
    useChatStore.setState({ chats: [seedChat()] });
    const { CoraStreamError } = await import('@/services/coraApi');
    const steps = [
      {
        agentName: 'Route the question',
        nodeName: 'Query Routing',
        kind: 'route',
        status: 'complete' as const,
        messages: ['Finding the best source'],
        nodeId: 'step-0',
      },
      {
        agentName: 'Compose the answer',
        nodeName: 'Answer Generation',
        kind: 'compose',
        status: 'error' as const,
        messages: ['Answer generation failed'],
        nodeId: 'step-1',
      },
    ];
    mockStream.mockRejectedValueOnce(
      new CoraStreamError('abc12345', 'I encountered an error processing your query.', steps)
    );

    await runRequest();

    const bot = getCurrentChat('chat-1')?.messages.find((m) => m.sender === 'bot');
    expect(bot?.status).toBe('error');
    expect(bot?.content).toBe('I encountered an error processing your query.');
    expect(bot?.agentReasoning).toHaveLength(2);
    expect(bot?.agentReasoning?.[1].status).toBe('error');
  });

  it('maps CoraApiError status to friendly copy', async () => {
    useChatStore.setState({ chats: [seedChat()] });
    const { CoraApiError } = await import('@/services/coraApi');
    mockStream.mockRejectedValueOnce(new CoraApiError('http', 'API request failed with status 500', 500));

    await runRequest();

    const bot = getCurrentChat('chat-1')?.messages.find((m) => m.sender === 'bot');
    expect(bot?.status).toBe('error');
    expect(bot?.content).toBe('The AI service had an internal error. Please try again in a moment.');
    expect(bot?.agentReasoning).toBeUndefined();
  });

  it('maps CoraApiError timeout to friendly copy', async () => {
    useChatStore.setState({ chats: [seedChat()] });
    const { CoraApiError } = await import('@/services/coraApi');
    mockStream.mockRejectedValueOnce(new CoraApiError('timeout', 'API request timeout'));

    await runRequest();

    const bot = getCurrentChat('chat-1')?.messages.find((m) => m.sender === 'bot');
    expect(bot?.content).toBe('The request timed out before a response was ready. Please retry, or try a shorter/more focused question.');
  });

  it('falls back to generic copy for untyped failures', async () => {
    useChatStore.setState({ chats: [seedChat()] });
    mockStream.mockRejectedValueOnce(new Error('internal server error'));

    await runRequest();

    const bot = getCurrentChat('chat-1')?.messages.find((m) => m.sender === 'bot');
    expect(bot?.status).toBe('error');
    expect(bot?.content).toBe("I'm sorry, I encountered an error. Please try again.");
    expect(bot?.agentReasoning).toBeUndefined();
  });
});
