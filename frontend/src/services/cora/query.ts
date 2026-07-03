import { sanitizeInput } from '@/lib/security';
import { API_ENDPOINT, API_TIMEOUT_MS, ENABLE_DEBUG_REASONS, IS_PROD } from './config';
import { buildAgentReasoning } from './agentReasoning';
import { ChatHistoryMessage, CoraResponse, QueryCoraOptions, QueryRequest, QueryResponse, CitationResponse, QuizResponse, ResponseMetadata } from './types';

export async function queryCora(
  question: string,
  conversationId?: string,
  history?: ChatHistoryMessage[],
  historySignature?: string,
  options: QueryCoraOptions = {}
): Promise<CoraResponse> {
  const { signal } = options;
  let abortSource: 'timeout' | 'external' | null = null;

  try {
    if (!question || typeof question !== 'string') {
      return {
        text: "I'm sorry, I couldn't process your request. Please provide a valid question.",
        agentReasoning: [],
      };
    }

    let sanitizedQuestion = question.trim();
    if (sanitizedQuestion.length > 8000) {
      sanitizedQuestion = sanitizedQuestion.substring(0, 8000);
    }
    sanitizedQuestion = sanitizeInput(sanitizedQuestion);

    const sanitizedConversationId = conversationId
      ? sanitizeInput(conversationId)
      : undefined;

    if (!API_ENDPOINT) {
      return {
        text: IS_PROD
          ? "I'm sorry, the AI service is not properly configured. Please contact the administrator."
          : 'AI service endpoint is not configured. Please set VITE_API_BASE in your .env file.',
        agentReasoning: [],
      };
    }

    if (import.meta.env.DEV) {
      console.log('Sending request to Cora API:', {
        url: API_ENDPOINT,
        question: sanitizedQuestion.substring(0, 50) + '...',
        conversationId: sanitizedConversationId,
        historyLength: history?.length ?? 0,
        historySignature: historySignature ? 'present' : 'absent',
        historyPreview: history?.slice(-2).map(h => ({ role: h.role, content: h.content.substring(0, 30) + '...' })),
      });
    }

    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };

    const controller = new AbortController();
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    let externalAbortHandler: (() => void) | undefined;
    if (signal) {
      signal.throwIfAborted();

      externalAbortHandler = () => {
        abortSource = 'external';
        controller.abort();
      };
      signal.addEventListener('abort', externalAbortHandler, { once: true });
    }

    const startTime = performance.now();

    try {
      const requestBody: QueryRequest = {
        text: sanitizedQuestion,
        include_debug: ENABLE_DEBUG_REASONS,
      };
      if (sanitizedConversationId) {
        requestBody.conversation_id = sanitizedConversationId;
      }
      if (history && history.length > 0) {
        requestBody.history = history.slice(-50);
      }
      if (historySignature) {
        requestBody.history_signature = historySignature;
      }

      timeoutId = setTimeout(() => {
        abortSource = 'timeout';
        controller.abort();
      }, API_TIMEOUT_MS);

      const response = await fetch(API_ENDPOINT, {
        method: 'POST',
        headers,
        signal: controller.signal,
        body: JSON.stringify(requestBody),
      });

      const duration = performance.now() - startTime;

      if (!response.ok) {
        let errorData: { message?: string; detail?: string } = {};
        try {
          const errorText = await response.text();
          if (import.meta.env.DEV) console.error('Backend error response:', errorText);
          try {
            errorData = JSON.parse(errorText);
          } catch {
            errorData = { message: errorText };
          }
        } catch (e) {
          if (import.meta.env.DEV) console.error('Failed to read error response:', e);
        }

        if (response.status === 401) {
          if (import.meta.env.DEV) console.error('Authentication failed:', errorData);
          return {
            text: 'Authentication failed. Please check your API configuration.',
            agentReasoning: [],
          };
        }

        if (response.status === 429) {
          return {
            text: 'The AI service is busy. Please try again in a moment.',
            agentReasoning: [],
          };
        }

        if (response.status === 503) {
          return {
            text: 'The AI service is starting up. Please try again in a moment.',
            agentReasoning: [],
          };
        }

        if (import.meta.env.DEV) {
          console.error('Cora API error:', {
            status: response.status,
            duration,
            error: errorData,
          });
        }
        throw new Error(`API request failed with status ${response.status}: ${errorData.message || errorData.detail || 'Unknown error'}`);
      }

      let parsedResult: unknown;
      try {
        parsedResult = await response.json();
      } catch (parseError) {
        const parseMessage = parseError instanceof Error ? parseError.message : 'Unknown parse error';
        throw new Error(`Invalid JSON response from Cora API: ${parseMessage}`);
      }

      if (typeof parsedResult !== 'object' || parsedResult === null) {
        throw new Error('Invalid API response format: expected an object payload');
      }

      const resultObject = parsedResult as Partial<QueryResponse>;

      if (typeof resultObject.answer !== 'string') {
        throw new Error('Invalid API response format: missing answer');
      }

      const result: QueryResponse = {
        answer: resultObject.answer,
        confidence: typeof resultObject.confidence === 'number' ? resultObject.confidence : 0,
        sources: Array.isArray(resultObject.sources)
          ? resultObject.sources.filter((source): source is string => typeof source === 'string')
          : [],
        conversation_id:
          typeof resultObject.conversation_id === 'string' ? resultObject.conversation_id : '',
        timestamp: typeof resultObject.timestamp === 'string' ? resultObject.timestamp : new Date().toISOString(),
        citations: (resultObject.citations && typeof resultObject.citations === 'object'
          ? resultObject.citations
          : null) as CitationResponse | null,
        reasoning_steps: Array.isArray(resultObject.reasoning_steps)
          ? resultObject.reasoning_steps
          : null,
        quiz: (resultObject.quiz && typeof resultObject.quiz === 'object'
          ? resultObject.quiz
          : null) as QuizResponse | null,
        metadata: (resultObject.metadata && typeof resultObject.metadata === 'object'
          ? resultObject.metadata
          : undefined) as ResponseMetadata | undefined,
        history_signature: typeof resultObject.history_signature === 'string'
          ? resultObject.history_signature
          : undefined,
      };

      const sourceCount = result.sources.length;
      const logConfidence = result.confidence;

      if (import.meta.env.DEV) {
        console.log('Cora API response received:', {
          duration,
          confidence: logConfidence,
          sourceCount,
        });
      }

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
      };
    } catch (fetchError) {
      const duration = performance.now() - startTime;

      if (fetchError instanceof DOMException && fetchError.name === 'AbortError') {
        if (abortSource === 'external') {
          throw fetchError;
        }
        if (import.meta.env.DEV) {
          console.error(`Cora API request timed out after ${API_TIMEOUT_MS / 1000} seconds`);
        }
        throw new Error(`API request timeout after ${API_TIMEOUT_MS / 1000}s`);
      }

      if (import.meta.env.DEV) {
        console.error('Cora request failed', { duration, error: fetchError });
      }
      throw fetchError;
    } finally {
      if (timeoutId !== undefined) {
        clearTimeout(timeoutId);
      }
      if (externalAbortHandler && signal) {
        signal.removeEventListener('abort', externalAbortHandler);
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError' && abortSource === 'external') {
      throw error;
    }

    const errorMessage = error instanceof Error ? error.message : 'Unknown error';
    const errorName = error instanceof Error ? error.name : 'Error';

    if (import.meta.env.DEV) {
      console.error(`Error querying Cora (${errorName}):`, error);
    } else {
      console.error(`AI service error (${errorName}): ${errorMessage}`);
    }

    throw error instanceof Error
      ? error
      : new Error('Unknown error connecting to AI service');
  }
}
