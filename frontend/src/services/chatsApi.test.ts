import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ChatsApiError, deleteChat, getChat, listChats } from './chatsApi';
import { apiFetch } from './apiFetch';
import { getUnseenRecommendations } from '@/components/chat/recommendationSelection';
import { detectTopics } from '@/store/chatStore.utils';

vi.mock('./apiFetch', () => ({
  apiFetch: vi.fn(),
}));

const mockFetch = vi.mocked(apiFetch);

const jsonResponse = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });

const makeTurn = (overrides: Record<string, unknown> = {}) => ({
  message_id: 'm1',
  answer_id: 'm1-answer',
  user_text: 'What is VM0048?',
  response: {
    answer: 'VM0048 is a Verra methodology.',
    confidence: 0.9,
    sources: ['knowledge_base'],
    conversation_id: 'chat-1',
    message_id: 'm1',
    answer_id: 'm1-answer',
    timestamp: '2024-01-02T03:04:05Z',
    citations: {
      count: 1,
      sources: ['doc.pdf'],
      details: [
        {
          source_name: 'doc.pdf',
          source_type: 'knowledge_base',
          relevance_score: 0.9,
          page_number: null,
          section: null,
          url: null,
          snippet: null,
        },
      ],
    },
    reasoning_steps: [
      { name: 'answer_generation', status: 'completed', duration_ms: 5, details: { summary: 'Done' } },
    ],
    metadata: { route: 'knowledge_base', total_time_ms: 12 },
    quiz: null,
    suggested_prompts: ['Follow-up?'],
  },
  created_at: '2024-01-02 03:04:05',
  ...overrides,
});

const makeDetail = (turns: unknown[]) => ({
  id: 'chat-1',
  title: 'What is VM0048?',
  created_at: '2024-01-02 03:04:05',
  updated_at: '2024-01-02 03:04:05',
  turns,
});

describe('listChats', () => {
  beforeEach(() => mockFetch.mockReset());

  it('maps summaries to chats with messagesLoaded false', async () => {
    mockFetch.mockResolvedValueOnce(
      jsonResponse(200, {
        chats: [
          { id: 'c1', title: 'First', updated_at: '2024-01-02 03:04:05' },
          { id: 'c2', title: 'Second', updated_at: '2024-01-01 00:00:00' },
        ],
      })
    );

    const chats = await listChats();

    expect(mockFetch).toHaveBeenCalledWith('/api/chats');
    expect(chats).toHaveLength(2);
    expect(chats[0].id).toBe('c1');
    expect(chats[0].title).toBe('First');
    expect(chats[0].messages).toEqual([]);
    expect(chats[0].messagesLoaded).toBe(false);
    expect(chats[0].shownRecommendations).toEqual([]);
    expect(chats[0].updatedAt).toBeInstanceOf(Date);
  });

  it('throws ChatsApiError on failure', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(500, {}));
    await expect(listChats()).rejects.toBeInstanceOf(ChatsApiError);
  });
});

describe('getChat', () => {
  beforeEach(() => mockFetch.mockReset());

  it('maps one server turn to a user message and a bot message', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(200, makeDetail([makeTurn()])));

    const chat = await getChat('chat-1');

    expect(mockFetch).toHaveBeenCalledWith('/api/chats/chat-1');
    expect(chat.messagesLoaded).toBe(true);
    expect(chat.messages).toHaveLength(2);

    const [user, bot] = chat.messages;
    expect(user.id).toBe('m1');
    expect(user.sender).toBe('user');
    expect(user.content).toBe('What is VM0048?');

    expect(bot.id).toBe('m1-answer');
    expect(bot.sender).toBe('bot');
    expect(bot.replyToMessageId).toBe('m1');
    expect(bot.status).toBe('complete');
    expect(bot.content).toBe('VM0048 is a Verra methodology.');
    expect(bot.citations?.count).toBe(1);
    expect(bot.citations?.details[0].source_name).toBe('doc.pdf');
    expect(bot.agentReasoning).toHaveLength(1);
    expect(bot.agentReasoning?.[0].agentName).toBe('answer_generation');
    expect(bot.suggestedPrompts).toEqual(['Follow-up?']);
    expect(bot.metadata?.route).toBe('knowledge_base');
  });

  it('uses the empty-KB text for a kb_empty turn', async () => {
    const turn = makeTurn({
      response: {
        ...((makeTurn().response) as Record<string, unknown>),
        answer: '',
        metadata: { route: 'knowledge_base', total_time_ms: 12, kb_empty: true },
      },
    });
    mockFetch.mockResolvedValueOnce(jsonResponse(200, makeDetail([turn])));

    const chat = await getChat('chat-1');

    expect(chat.messages[1].content).toContain("couldn't find anything in the knowledge base");
  });

  it('replays recommendations like three live turns', async () => {
    const texts = [
      'Tell me about carbon projects',
      'What is the price of carbon credits?',
      'Show me a REDD+ case study',
    ];
    const turns = texts.map((text, i) =>
      makeTurn({
        message_id: `m${i + 1}`,
        user_text: text,
        response: {
          ...((makeTurn().response) as Record<string, unknown>),
          message_id: `m${i + 1}`,
          answer_id: `m${i + 1}-answer`,
        },
      })
    );
    mockFetch.mockResolvedValueOnce(jsonResponse(200, makeDetail(turns)));

    const chat = await getChat('chat-1');

    // Expected = the same shared selection function run over the same texts
    // in order, which is exactly what the live path does turn by turn (D30).
    const shown: string[] = [];
    const expected: string[][] = [];
    for (const text of texts) {
      const { recommendationIds } = getUnseenRecommendations(detectTopics(text), shown, text);
      expected.push(recommendationIds);
      shown.push(...recommendationIds);
    }

    const botMessages = chat.messages.filter((m) => m.sender === 'bot');
    expect(botMessages).toHaveLength(3);
    botMessages.forEach((bot, i) => {
      expect(bot.triggeredRecommendationIds ?? []).toEqual(expected[i]);
    });
    expect(chat.shownRecommendations).toEqual(shown);
  });

  it('throws ChatsApiError with status on 404', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(404, { detail: 'Chat not found' }));
    try {
      await getChat('gone');
      expect.unreachable('should have thrown');
    } catch (error) {
      expect(error).toBeInstanceOf(ChatsApiError);
      expect((error as ChatsApiError).status).toBe(404);
    }
  });
});

describe('deleteChat', () => {
  beforeEach(() => mockFetch.mockReset());

  it('sends a DELETE request', async () => {
    mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await deleteChat('chat-1');

    expect(mockFetch).toHaveBeenCalledWith('/api/chats/chat-1', { method: 'DELETE' });
  });

  it('throws ChatsApiError on non-2xx', async () => {
    mockFetch.mockResolvedValueOnce(jsonResponse(500, {}));
    await expect(deleteChat('chat-1')).rejects.toBeInstanceOf(ChatsApiError);
  });
});
