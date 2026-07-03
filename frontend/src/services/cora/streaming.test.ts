import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { queryCoraStream } from './streaming';

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

function createSSEStream(chunks: string[]): ReadableStream<Uint8Array> {
  let index = 0;
  return new ReadableStream({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(new TextEncoder().encode(chunks[index]));
        index++;
      } else {
        controller.close();
      }
    },
  });
}

describe('queryCoraStream', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('handles non-SSE success response (fallback to JSON)', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          answer: 'Fallback answer',
          confidence: 0.8,
          sources: [],
          conversation_id: 'conv-2',
          timestamp: new Date().toISOString(),
        }),
        {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }
      )
    );

    const onResult = vi.fn();
    const onDone = vi.fn();

    const result = await queryCoraStream('Hello', undefined, undefined, undefined, {
      onResult,
      onDone,
    });

    expect(result.text).toBe('Fallback answer');
    expect(onResult).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it('does NOT retry on 403 — returns error response to caller', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'Session expired' }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const onError = vi.fn();

    await expect(
      queryCoraStream('Hello', undefined, undefined, undefined, { onError })
    ).rejects.toThrow('API request failed with status 403');

    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('returns auth error on 401 without throwing', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const onError = vi.fn();
    const result = await queryCoraStream('Hello', undefined, undefined, undefined, { onError });

    expect(result.text).toBe('Authentication failed. Please check your API configuration.');
    expect(onError).toHaveBeenCalledWith('auth', expect.any(String));
  });

  it('returns busy message on 429 without throwing', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Rate limited' }), {
        status: 429,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    const onError = vi.fn();
    const result = await queryCoraStream('Hello', undefined, undefined, undefined, { onError });

    expect(result.text).toContain("AI service is busy");
    expect(onError).toHaveBeenCalledWith('rate_limit', expect.any(String));
  });

  it('processes SSE stream events correctly', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    const chunks = [
      'event: status\ndata: {"event":"status","status":"processing","stage":"Searching","progress":25}\n\n',
      'event: status\ndata: {"event":"status","status":"processing","stage":"Generating","progress":75}\n\n',
      'event: result\ndata: {"answer":"Streamed answer","confidence":0.9,"sources":[],"conversation_id":"conv-3","timestamp":"2024-01-01T00:00:00Z"}\n\n',
      'event: done\ndata: {}\n\n',
    ];

    mockFetch.mockResolvedValueOnce(
      new Response(createSSEStream(chunks), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    );

    const onStatus = vi.fn();
    const onResult = vi.fn();
    const onDone = vi.fn();

    const result = await queryCoraStream('Hello', undefined, undefined, undefined, {
      onStatus,
      onResult,
      onDone,
    });

    expect(onStatus).toHaveBeenCalledTimes(2);
    expect(onStatus).toHaveBeenNthCalledWith(1, { event: 'status', status: 'processing', message: 'Searching (25%)', stage: 'Searching', progress: 25 });
    expect(onStatus).toHaveBeenNthCalledWith(2, { event: 'status', status: 'processing', message: 'Generating (75%)', stage: 'Generating', progress: 75 });
    expect(onResult).toHaveBeenCalledTimes(1);
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(result.text).toBe('Streamed answer');
  });

  it('throws on 503 (unlike queryCora which returns a startup message)', async () => {
    // NOTE: streaming.ts throws on 503, while query.ts returns a startup message.
    // This is a behavioral inconsistency that callers should be aware of.
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ message: 'Starting up' }), {
        status: 503,
        headers: { 'Content-Type': 'application/json' },
      })
    );

    await expect(queryCoraStream('Hello')).rejects.toThrow('API request failed with status 503');
  });

  it('throws when SSE stream ends without a result event', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(
      new Response(createSSEStream([]), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    );

    await expect(queryCoraStream('Hello')).rejects.toThrow(
      'Stream ended without receiving a result'
    );
  });

  it('handles malformed SSE events without crashing', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    const chunks = [
      'event: status\ndata: not-valid-json\n\n',
      'event: result\ndata: {"answer":"Partial result","confidence":0.5,"sources":[],"conversation_id":"conv-4","timestamp":"2024-01-01T00:00:00Z"}\n\n',
      'event: done\ndata: {}\n\n',
    ];

    mockFetch.mockResolvedValueOnce(
      new Response(createSSEStream(chunks), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    );

    const onStatus = vi.fn();
    const onResult = vi.fn();

    const result = await queryCoraStream('Hello', undefined, undefined, undefined, {
      onStatus,
      onResult,
    });

    // Malformed status should be skipped; valid result should still be processed
    expect(onStatus).toHaveBeenCalledTimes(0); // malformed status not parsed
    expect(onResult).toHaveBeenCalledTimes(1);
    expect(result.text).toBe('Partial result');
  });

  it('handles network errors by throwing', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockRejectedValueOnce(new Error('Network failure'));

    await expect(queryCoraStream('Hello')).rejects.toThrow();
  });

  it('respects abort signal', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    const chunks = [
      'event: status\ndata: {"event":"status","status":"processing","stage":"Searching","progress":25}\n\n',
    ];

    mockFetch.mockResolvedValueOnce(
      new Response(createSSEStream(chunks), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    );

    const controller = new AbortController();

    // Start the request then abort immediately
    // signal goes in QueryCoraOptions (6th param), not callbacks (5th)
    const promise = queryCoraStream(
      'Hello',
      undefined,
      undefined,
      undefined,
      {},
      { signal: controller.signal }
    );

    controller.abort();

    // Should either resolve or reject, not hang
    await expect(promise).rejects.toBeDefined();
  });

  it('processes SSE stream with embedded newlines in data', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    const chunks = [
      'event: result\ndata: {"answer":"Line 1\\nLine 2","confidence":1,"sources":[],"conversation_id":"conv-5","timestamp":"2024-01-01T00:00:00Z"}\n\n',
      'event: done\ndata: {}\n\n',
    ];

    mockFetch.mockResolvedValueOnce(
      new Response(createSSEStream(chunks), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    );

    const result = await queryCoraStream('Hello');
    expect(result.text).toBe('Line 1\nLine 2');
  });
});
