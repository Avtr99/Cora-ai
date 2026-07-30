import { describe, it, expect } from 'vitest';
import { buildProtocolHistory } from './useBotResponse';
import type { Chat, Message } from '@/store/chatStore.types';
import type { ChatHistoryMessage } from '@/services/cora/types';

const createMessage = (overrides: Partial<Message> = {}): Message => ({
  id: 'msg-1',
  content: 'Hello',
  sender: 'user',
  timestamp: new Date('2024-01-01'),
  ...overrides,
});

const createChat = (overrides: Partial<Chat> = {}): Chat => ({
  id: 'chat-1',
  title: 'Test Chat',
  messages: [createMessage()],
  createdAt: new Date('2024-01-01'),
  shownRecommendations: [],
  ...overrides,
});

describe('buildProtocolHistory', () => {
  it('echoes the signed history and signature when present', () => {
    const signedHistory: ChatHistoryMessage[] = [
      { role: 'user', content: 'What is VM0048?' },
      { role: 'assistant', content: 'VM0048 is a Verra methodology.' },
    ];
    const chat = createChat({
      history: signedHistory,
      historySignature: 'sig-abc',
      messages: [createMessage()],
    });
    const result = buildProtocolHistory(chat, 'msg-1');
    expect(result.protocolHistory).toEqual(signedHistory);
    expect(result.requestHistorySignature).toBe('sig-abc');
  });

  it('drops signature when signed history is missing (legacy transition)', () => {
    const chat = createChat({
      history: undefined,
      historySignature: 'sig-legacy',
      messages: [createMessage({ id: 'msg-1', sender: 'user' })],
    });
    const result = buildProtocolHistory(chat, 'msg-1');
    expect(result.protocolHistory).toBeUndefined();
    expect(result.requestHistorySignature).toBeUndefined();
  });

  it('sends unsigned history when signature is missing (dev/unsigned backend mode)', () => {
    const signedHistory: ChatHistoryMessage[] = [
      { role: 'user', content: 'Hello' },
      { role: 'assistant', content: 'Hi there' },
    ];
    const chat = createChat({
      history: signedHistory,
      historySignature: undefined,
    });
    const result = buildProtocolHistory(chat, 'msg-1');
    expect(result.protocolHistory).toEqual(signedHistory);
    expect(result.requestHistorySignature).toBeUndefined();
  });

  it('derives fallback from display messages and excludes pending + current message', () => {
    const messages: Message[] = [
      createMessage({ id: 'm1', sender: 'user', content: 'First?', status: 'complete' }),
      createMessage({ id: 'm2', sender: 'bot', content: 'Answer one', status: 'complete' }),
      createMessage({ id: 'm3', sender: 'user', content: 'Second?', status: 'complete' }),
      createMessage({ id: 'm4', sender: 'user', content: 'Currently typing...', status: 'pending' }),
    ];
    const chat = createChat({ messages });
    const result = buildProtocolHistory(chat, 'm3');
    expect(result.protocolHistory).toEqual([
      { role: 'user', content: 'First?' },
      { role: 'assistant', content: 'Answer one' },
    ]);
    expect(result.requestHistorySignature).toBeUndefined();
  });

  it('caps fallback history at 50 and keeps the last entries', () => {
    const messages: Message[] = Array.from({ length: 60 }, (_, i) =>
      createMessage({ id: `m${i}`, sender: i % 2 === 0 ? 'user' : 'bot', content: `Msg ${i}`, status: 'complete' })
    );
    const currentId = 'm60';
    messages.push(createMessage({ id: currentId, sender: 'user', content: 'Current', status: 'complete' }));
    const chat = createChat({ messages });
    const result = buildProtocolHistory(chat, currentId);
    expect(result.protocolHistory).toHaveLength(50);
    expect(result.protocolHistory?.[0]).toEqual({ role: 'user', content: 'Msg 10' });
    expect(result.protocolHistory?.at(-1)).toEqual({ role: 'assistant', content: 'Msg 59' });
  });

  it('excludes the current user message even when it is not pending', () => {
    const messages: Message[] = [
      createMessage({ id: 'm1', sender: 'user', content: 'First?', status: 'complete' }),
      createMessage({ id: 'm2', sender: 'bot', content: 'Answer one', status: 'complete' }),
      createMessage({ id: 'm3', sender: 'user', content: 'Current', status: 'complete' }),
    ];
    const chat = createChat({ messages });
    const result = buildProtocolHistory(chat, 'm3');
    expect(result.protocolHistory).toEqual([
      { role: 'user', content: 'First?' },
      { role: 'assistant', content: 'Answer one' },
    ]);
  });
});
