import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { queryCora } from './query';

vi.mock('./config', () => ({
  API_ENDPOINT: '/api/cora-query',
  API_STREAM_ENDPOINT: '/api/cora-query-stream',
  API_TIMEOUT_MS: 60000,
  ENABLE_DEBUG_REASONS: false,
  IS_PROD: false,
}));

vi.mock('@/lib/security', () => ({
  sanitizeInput: vi.fn((input: string) => input),
}));

vi.mock('./agentReasoning', () => ({
  buildAgentReasoning: vi.fn().mockReturnValue([]),
}));

describe('queryCora', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('returns parsed answer on successful response', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          answer: 'Test answer',
          confidence: 0.95,
          sources: ['source1'],
          conversation_id: 'conv-1',
          timestamp: '2024-01-01T00:00:00Z',
        }),
        { status: 200, headers: { 'Content-Type': 'application/json' } }
      )
    );

    const result = await queryCora('Hello');

    expect(result.text).toBe('Test answer');
    expect(result.confidence).toBe(0.95);
    expect(result.sources).toEqual(['source1']);
    expect(result.conversationId).toBe('conv-1');
  });

  it('does NOT retry on 403 — propagates as error to caller', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Session expired' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    // queryCora throws on non-2xx after logging specific codes
    await expect(queryCora('Hello')).rejects.toThrow('API request failed with status 403');

    // Verify fetch was called exactly once (no retry)
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('returns busy message on 429 without throwing', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Rate limited' }), {
        status: 429,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const result = await queryCora('Hello');

    expect(result.text).toContain("AI service is busy");
    expect(result.agentReasoning).toEqual([]);
  });

  it('returns auth error on 401 without throwing', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const result = await queryCora('Hello');

    expect(result.text).toBe('Authentication failed. Please check your API configuration.');
    expect(result.agentReasoning).toEqual([]);
  });

  it('returns startup message on 503 without throwing', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Starting up' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const result = await queryCora('Hello');

    expect(result.text).toBe('The AI service is starting up. Please try again in a moment.');
    expect(result.agentReasoning).toEqual([]);
  });

  it('throws on invalid JSON response', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response('not-json', {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    await expect(queryCora('Hello')).rejects.toThrow('Invalid JSON response');
  });

  it('throws when answer field is missing', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ confidence: 0.5 }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    await expect(queryCora('Hello')).rejects.toThrow('missing answer');
  });
});
