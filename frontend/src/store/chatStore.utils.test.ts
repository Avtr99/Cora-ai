import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  generateId,
  generateChatTitle,
  validateAndSanitizeChatHistory,
  detectTopics,
} from './chatStore.utils';
import type { Chat, Message } from './chatStore.types';

// Mock security module to avoid DOMPurify DOM dependency
vi.mock('@/lib/security', () => ({
  sanitizeInput: (input: string) => input,
  sanitizeHTML: (html: string) => html,
}));

describe('generateId', () => {
  it('generates unique IDs across multiple calls', () => {
    const ids = new Set<string>();
    for (let i = 0; i < 100; i++) {
      ids.add(generateId());
    }
    expect(ids.size).toBe(100);
  });

  it('returns a non-empty string', () => {
    const id = generateId();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);
  });
});

describe('generateChatTitle', () => {
  it('returns short messages unchanged', () => {
    expect(generateChatTitle('Hello world')).toBe('Hello world');
  });

  it('truncates long messages to 30 chars with ellipsis', () => {
    const long = 'This is a very long message that exceeds thirty characters';
    expect(generateChatTitle(long)).toBe('This is a very long message th...');
  });

  it('handles exactly 30 characters without ellipsis', () => {
    const exact = 'a'.repeat(30);
    expect(generateChatTitle(exact)).toBe(exact);
  });

  it('handles empty string', () => {
    expect(generateChatTitle('')).toBe('');
  });
});

describe('validateAndSanitizeChatHistory', () => {
  const validMessage: Message = {
    id: 'msg-1',
    content: 'Hello',
    sender: 'user',
    timestamp: new Date('2024-01-01'),
  };

  const validChat: Chat = {
    id: 'chat-1',
    title: 'Test Chat',
    messages: [validMessage],
    createdAt: new Date('2024-01-01'),
    shownRecommendations: [],
  };

  it('returns valid chats unchanged', () => {
    const result = validateAndSanitizeChatHistory([validChat]);
    expect(result).toHaveLength(1);
    expect(result[0].id).toBe('chat-1');
    expect(result[0].messages).toHaveLength(1);
  });

  it('returns empty array for non-array input', () => {
    expect(validateAndSanitizeChatHistory(null)).toEqual([]);
    expect(validateAndSanitizeChatHistory({})).toEqual([]);
    expect(validateAndSanitizeChatHistory('string')).toEqual([]);
  });

  it('filters out chats with invalid id', () => {
    const invalidChat = { ...validChat, id: '' };
    const result = validateAndSanitizeChatHistory([invalidChat]);
    expect(result).toHaveLength(0);
  });

  it('filters out chats with non-string title', () => {
    const invalidChat = { ...validChat, title: 123 };
    const result = validateAndSanitizeChatHistory([invalidChat]);
    expect(result).toHaveLength(0);
  });

  it('filters out chats with non-array messages', () => {
    const invalidChat = { ...validChat, messages: 'not-array' };
    const result = validateAndSanitizeChatHistory([invalidChat]);
    expect(result).toHaveLength(0);
  });

  it('filters out invalid messages within valid chats', () => {
    const chatWithBadMessages = {
      ...validChat,
      messages: [
        validMessage,
        { id: '', content: 'no id', sender: 'user', timestamp: new Date() },
        { id: 'msg-2', content: 123, sender: 'user', timestamp: new Date() },
        { id: 'msg-3', content: 'ok', sender: 'unknown', timestamp: new Date() },
        null,
        'not an object',
      ],
    };
    const result = validateAndSanitizeChatHistory([chatWithBadMessages]);
    expect(result).toHaveLength(1);
    expect(result[0].messages).toHaveLength(1);
    expect(result[0].messages[0].id).toBe('msg-1');
  });

  it('sanitizes message content', () => {
    const chatWithXSS = {
      ...validChat,
      messages: [
        {
          ...validMessage,
          content: '<script>alert("xss")</script>Hello',
        },
      ],
    };
    const result = validateAndSanitizeChatHistory([chatWithXSS]);
    // sanitizeHTML is mocked to pass-through, but in real usage it strips script tags
    expect(result[0].messages[0].content).toBe('<script>alert("xss")</script>Hello');
  });

  it('handles missing timestamps by using current date', () => {
    const chatNoTimestamp = {
      ...validChat,
      messages: [{ id: 'msg-1', content: 'Hello', sender: 'user' }],
    };
    const result = validateAndSanitizeChatHistory([chatNoTimestamp]);
    expect(result[0].messages[0].timestamp).toBeInstanceOf(Date);
  });

  it('validates message status enum', () => {
    const chatWithStatuses = {
      ...validChat,
      messages: [
        { ...validMessage, status: 'pending' },
        { ...validMessage, id: 'msg-2', status: 'complete' },
        { ...validMessage, id: 'msg-3', status: 'error' },
        { ...validMessage, id: 'msg-4', status: 'cancelled' },
        { ...validMessage, id: 'msg-5', status: 'invalid-status' },
      ],
    };
    const result = validateAndSanitizeChatHistory([chatWithStatuses]);
    // All 5 messages are kept; invalid status becomes undefined
    expect(result[0].messages).toHaveLength(5);
    // The one with 'invalid-status' should have status undefined
    const invalidStatusMsg = result[0].messages.find(m => m.id === 'msg-5');
    expect(invalidStatusMsg?.status).toBeUndefined();
  });

  it('validates shownRecommendations array', () => {
    const chatWithRecs = {
      ...validChat,
      shownRecommendations: ['rec-1', 'rec-2', 123, null],
    };
    const result = validateAndSanitizeChatHistory([chatWithRecs]);
    // Non-string entries cause the entire array to be replaced with []
    expect(result[0].shownRecommendations).toEqual([]);
  });

  it('sanitizes backendConversationId and historySignature', () => {
    const chatWithBackend = {
      ...validChat,
      backendConversationId: 'backend-123',
      historySignature: 'sig-abc',
    };
    const result = validateAndSanitizeChatHistory([chatWithBackend]);
    expect(result[0].backendConversationId).toBe('backend-123');
    expect(result[0].historySignature).toBe('sig-abc');
  });

  it('handles completely empty array', () => {
    expect(validateAndSanitizeChatHistory([])).toEqual([]);
  });
});

describe('detectTopics', () => {
  it('detects project-related keywords', () => {
    expect(detectTopics('Tell me about carbon projects')).toContain('project');
    expect(detectTopics('What methodologies are used?')).toContain('project');
    expect(detectTopics('Show me a case study')).toContain('project');
    expect(detectTopics('What about renewable energy?')).toContain('project');
  });

  it('does not detect project for unrelated words', () => {
    expect(detectTopics('projection mapping is cool')).not.toContain('project');
    expect(detectTopics('hello world')).not.toContain('project');
  });

  it('detects pricing with carbon context', () => {
    expect(detectTopics('What is the price of carbon credits?')).toContain('pricing');
    expect(detectTopics('How much do offsets cost?')).toContain('pricing');
    expect(detectTopics('Carbon credit pricing analysis')).toContain('pricing');
  });

  it('detects explicit pricing phrases without carbon context', () => {
    expect(detectTopics('What is the price per ton?')).toContain('pricing');
    expect(detectTopics('Show me $/t data')).toContain('pricing');
    expect(detectTopics('Credit price trends')).toContain('pricing');
  });

  it('does not detect pricing for generic price mentions without carbon context', () => {
    expect(detectTopics('What is the price of coffee?')).not.toContain('pricing');
    expect(detectTopics('Apple stock price')).not.toContain('pricing');
  });

  it('detects both topics when applicable', () => {
    const topics = detectTopics('What is the carbon price of REDD+ projects?');
    expect(topics).toContain('project');
    expect(topics).toContain('pricing');
  });

  it('returns empty array for irrelevant messages', () => {
    expect(detectTopics('Hello, how are you?')).toEqual([]);
    expect(detectTopics('The weather is nice today')).toEqual([]);
  });

  it('handles VM0048 methodology mentions', () => {
    expect(detectTopics('Tell me about VM0048')).toContain('project');
    expect(detectTopics('VM 0048 methodology')).toContain('project');
  });
});
