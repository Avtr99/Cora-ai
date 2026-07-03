import { sanitizeInput } from '@/lib/security';
import { API_STREAM_ENDPOINT, API_TIMEOUT_MS, ENABLE_DEBUG_REASONS, IS_PROD } from './config';
import { buildAgentReasoning } from './agentReasoning';
import {
  ChatHistoryMessage,
  CoraResponse,
  QueryCoraOptions,
  QueryRequest,
  QueryResponse,
  SSEEvent,
  StreamingCallbacks,
} from './types';

/**
 * Lightweight runtime validation for the backend query response.
 *
 * We trust the backend but still guard against malformed JSON / proxies
 * returning unexpected shapes. Only `answer` is required; every other
 * field gets a sensible default so the UI can degrade gracefully.
 */
function validateQueryResponse(value: unknown): QueryResponse {
  if (value === null || typeof value !== 'object') {
    throw new Error('Invalid response: expected an object');
  }

  const obj = value as Record<string, unknown>;

  if (typeof obj.answer !== 'string') {
    throw new Error('Invalid response: missing or non-string answer');
  }

  const ensureArray = (key: string): string[] => {
    const candidate = obj[key];
    return Array.isArray(candidate) && candidate.every((i) => typeof i === 'string')
      ? (candidate as string[])
      : [];
  };

  return {
    answer: obj.answer,
    confidence: typeof obj.confidence === 'number' ? obj.confidence : 0,
    sources: ensureArray('sources'),
    conversation_id: typeof obj.conversation_id === 'string' ? obj.conversation_id : '',
    timestamp: typeof obj.timestamp === 'string' ? obj.timestamp : '',
    citations: (obj.citations as QueryResponse['citations']) ?? null,
    reasoning_steps: (obj.reasoning_steps as QueryResponse['reasoning_steps']) ?? null,
    metadata: obj.metadata as QueryResponse['metadata'],
    quiz: (obj.quiz as QueryResponse['quiz']) ?? null,
    history_signature: typeof obj.history_signature === 'string' ? obj.history_signature : undefined,
    suggested_prompts: ensureArray('suggested_prompts'),
  };
}

export async function queryCoraStream(
  question: string,
  conversationId?: string,
  history?: ChatHistoryMessage[],
  historySignature?: string,
  callbacks: StreamingCallbacks = {},
  options: QueryCoraOptions = {}
): Promise<CoraResponse> {
  const { signal } = options;
  const { onStatus, onToken, onReplace, onResult, onError, onDone } = callbacks;

  if (!question || typeof question !== 'string') {
    const errorResponse: CoraResponse = {
      text: "I'm sorry, I couldn't process your request. Please provide a valid question.",
      agentReasoning: [],
    };
    onError?.('validation', 'Invalid question');
    return errorResponse;
  }

  let sanitizedQuestion = question.trim();
  if (sanitizedQuestion.length > 8000) {
    sanitizedQuestion = sanitizedQuestion.substring(0, 8000);
  }
  sanitizedQuestion = sanitizeInput(sanitizedQuestion);

  const sanitizedConversationId = conversationId
    ? sanitizeInput(conversationId)
    : undefined;

  if (!API_STREAM_ENDPOINT) {
    const errorResponse: CoraResponse = {
      text: IS_PROD
        ? "I'm sorry, the AI service is not properly configured. Please contact the administrator."
        : 'AI service endpoint is not configured. Please set VITE_API_BASE in your .env file.',
      agentReasoning: [],
    };
    onError?.('config', 'Endpoint not configured');
    return errorResponse;
  }

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  const requestBody: QueryRequest = {
    text: sanitizedQuestion,
    include_debug: ENABLE_DEBUG_REASONS,
  };
  if (sanitizedConversationId) {
    requestBody.conversation_id = sanitizedConversationId;
  }
  // Include conversation history for context-aware answers (max 50 messages)
  if (history && history.length > 0) {
    requestBody.history = history.slice(-50);
  }
  if (historySignature) {
    requestBody.history_signature = historySignature;
  }

  const controller = new AbortController();
  let timeoutId: ReturnType<typeof setTimeout> | undefined;

  let externalAbortHandler: (() => void) | undefined;
  if (signal) {
    signal.throwIfAborted();
    externalAbortHandler = () => controller.abort();
    signal.addEventListener('abort', externalAbortHandler, { once: true });
  }

  try {
    timeoutId = setTimeout(() => controller.abort(), API_TIMEOUT_MS);

    const response = await fetch(`${API_STREAM_ENDPOINT}?tokens=false`, {
      method: 'POST',
      headers,
      body: JSON.stringify(requestBody),
      signal: controller.signal,
    });

    if (!response.ok) {
      let errorData: { message?: string; detail?: string } = {};
      try {
        const errorText = await response.text();
        console.error('[SSE] Backend error response:', errorText);
        try {
          errorData = JSON.parse(errorText);
        } catch {
          errorData = { message: errorText };
        }
      } catch (e) {
        console.error('[SSE] Failed to read error response:', e);
      }

      if (response.status === 401) {
        onError?.('auth', 'Authentication failed. Please check your API configuration.');
        return {
          text: 'Authentication failed. Please check your API configuration.',
          agentReasoning: [],
        };
      }

      if (response.status === 429) {
        onError?.('rate_limit', 'The AI service is busy. Please try again in a moment.');
        return {
          text: 'The AI service is busy. Please try again in a moment.',
          agentReasoning: [],
        };
      }

      throw new Error(`API request failed with status ${response.status}: ${errorData.message || errorData.detail || 'Unknown error'}`);
    }

    const contentType = response.headers.get('Content-Type') || '';
    if (!contentType.includes('text/event-stream')) {
      console.warn('[SSE] Expected text/event-stream but got:', contentType);
      const rawResult = await response.json();
      const result = validateQueryResponse(rawResult);
      const agentReasoning = buildAgentReasoning(result);
      const coraResponse: CoraResponse = {
        text: result.answer,
        confidence: result.confidence,
        sources: result.sources,
        conversationId: result.conversation_id,
        timestamp: result.timestamp,
        agentReasoning,
        citations: result.citations,
        metadata: result.metadata,
        quiz: result.quiz,
        historySignature: result.history_signature,
        suggestedPrompts: result.suggested_prompts,
      };
      onResult?.(coraResponse);
      onDone?.();
      return coraResponse;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      throw new Error('Response body is not readable');
    }

    const decoder = new TextDecoder();
    let buffer = '';
    let finalResponse: CoraResponse | null = null;

    const normalizeStatusMessage = (event: SSEEvent): string => {
      if (event.event !== 'status') return '';

      if (event.message && event.message.trim().length > 0) {
        return event.message;
      }

      const stageText = event.stage?.trim();
      if (stageText) {
        if (typeof event.progress === 'number' && Number.isFinite(event.progress)) {
          return `${stageText} (${Math.round(event.progress)}%)`;
        }
        return stageText;
      }

      return event.status || 'processing';
    };

    const buildResultResponse = (result: QueryResponse): CoraResponse => {
      const agentReasoning = buildAgentReasoning(result);
      return {
        text: result.answer,
        confidence: result.confidence,
        sources: result.sources,
        conversationId: result.conversation_id,
        timestamp: result.timestamp,
        agentReasoning,
        citations: result.citations,
        metadata: result.metadata,
        quiz: result.quiz,
        historySignature: result.history_signature,
        suggestedPrompts: result.suggested_prompts,
      };
    };

    const extractQueryResponse = (parsed: Record<string, unknown>): QueryResponse | null => {
      if (typeof parsed.answer === 'string') {
        return validateQueryResponse(parsed);
      }

      const candidates = [parsed.payload, parsed.data, parsed.result];
      for (const candidate of candidates) {
        if (!candidate || typeof candidate !== 'object') continue;
        if (typeof (candidate as Record<string, unknown>).answer === 'string') {
          return validateQueryResponse(candidate);
        }
      }

      return null;
    };

    try {
      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        const events = buffer.split('\n\n');
        buffer = events.pop() || '';

        for (const eventStr of events) {
          if (!eventStr.trim()) continue;

          const lines = eventStr.split('\n');
          let explicitEventType: string | undefined;
          const dataLines: string[] = [];

          for (const rawLine of lines) {
            const line = rawLine.trimEnd();
            if (!line || line.startsWith(':')) continue;

            if (line.startsWith('event:')) {
              explicitEventType = line.slice('event:'.length).trim();
              continue;
            }

            if (line.startsWith('data:')) {
              dataLines.push(line.slice('data:'.length).trimStart());
            }
          }

          if (dataLines.length === 0) {
            continue;
          }

          const jsonStr = dataLines.join('\n');

          try {
            const parsed = JSON.parse(jsonStr) as Record<string, unknown>;
            let normalizedEvent: SSEEvent | null = null;

            const inferredType = explicitEventType
              || (typeof parsed.event === 'string' ? parsed.event : undefined)
              || (typeof parsed.type === 'string' ? parsed.type : undefined);

            if (inferredType === 'status') {
              normalizedEvent = {
                event: 'status',
                status: typeof parsed.status === 'string' ? parsed.status : undefined,
                message: typeof parsed.message === 'string' ? parsed.message : undefined,
                stage: typeof parsed.stage === 'string' ? parsed.stage : undefined,
                progress: typeof parsed.progress === 'number' ? parsed.progress : undefined,
              };
            } else if (inferredType === 'result') {
              const resultPayload = extractQueryResponse(parsed);
              if (resultPayload) {
                normalizedEvent = {
                  event: 'result',
                  payload: resultPayload,
                };
              }
            } else if (inferredType === 'token') {
              if (typeof parsed.chunk === 'string') {
                normalizedEvent = {
                  event: 'token',
                  chunk: parsed.chunk,
                };
              }
            } else if (inferredType === 'replace') {
              normalizedEvent = { event: 'replace' };
            } else if (inferredType === 'done') {
              normalizedEvent = { event: 'done' };
            } else if (inferredType === 'error') {
              normalizedEvent = {
                event: 'error',
                error_id: typeof parsed.error_id === 'string' ? parsed.error_id : 'stream',
                message: typeof parsed.message === 'string' ? parsed.message : 'Streaming error',
              };
            } else if (
              typeof parsed.status === 'string' ||
              typeof parsed.stage === 'string' ||
              typeof parsed.progress === 'number'
            ) {
              normalizedEvent = {
                event: 'status',
                status: typeof parsed.status === 'string' ? parsed.status : undefined,
                message: typeof parsed.message === 'string' ? parsed.message : undefined,
                stage: typeof parsed.stage === 'string' ? parsed.stage : undefined,
                progress: typeof parsed.progress === 'number' ? parsed.progress : undefined,
              };
            } else {
              const resultPayload = extractQueryResponse(parsed);
              if (resultPayload) {
                normalizedEvent = {
                  event: 'result',
                  payload: resultPayload,
                };
              }
            }

            if (!normalizedEvent) {
              if (import.meta.env.DEV) {
                console.warn('[SSE] Ignoring unrecognized stream payload:', parsed);
              }
              continue;
            }

            switch (normalizedEvent.event) {
              case 'status': {
                onStatus?.({
                  event: 'status',
                  status: normalizedEvent.status,
                  message: normalizeStatusMessage(normalizedEvent),
                  stage: normalizedEvent.stage,
                  progress: normalizedEvent.progress,
                });
                break;
              }

              case 'token': {
                onToken?.(normalizedEvent.chunk);
                break;
              }

              case 'replace': {
                onReplace?.();
                break;
              }

              case 'result': {
                finalResponse = buildResultResponse(normalizedEvent.payload);
                onResult?.(finalResponse);
                break;
              }

              case 'done':
                onDone?.();
                break;

              case 'error':
                console.error('[SSE] Error event:', normalizedEvent.error_id, normalizedEvent.message);
                onError?.(normalizedEvent.error_id, normalizedEvent.message);
                throw new Error(`Server error [${normalizedEvent.error_id}]: ${normalizedEvent.message}`);
            }
          } catch (parseError) {
            if (parseError instanceof SyntaxError) {
              console.warn('[SSE] Failed to parse event JSON:', jsonStr);
            } else {
              throw parseError;
            }
          }
        }
      }
    } finally {
      reader.releaseLock();
    }

    if (!finalResponse) {
      throw new Error('Stream ended without receiving a result');
    }

    return finalResponse;
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      if (signal?.aborted) {
        throw error;
      }
      console.error(`[SSE] Request timed out after ${API_TIMEOUT_MS / 1000} seconds`);
      throw new Error(`API request timeout after ${API_TIMEOUT_MS / 1000}s`);
    }

    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    console.error('[SSE] Streaming request failed:', errorMessage);
    throw error instanceof Error ? error : new Error('Unknown error connecting to AI service');
  } finally {
    if (timeoutId !== undefined) {
      clearTimeout(timeoutId);
    }
    if (externalAbortHandler && signal) {
      signal.removeEventListener('abort', externalAbortHandler);
    }
  }
}
