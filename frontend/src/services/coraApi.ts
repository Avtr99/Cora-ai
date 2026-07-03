/**
 * API facade for interacting with the Cora backend.
 *
 * The implementation is split into focused modules under `src/services/cora/`.
 * This file intentionally re-exports public API members to preserve import compatibility.
 */

export type {
  AgentReasoningStep,
  ChatHistoryMessage,
  CoraResponse,
  CitationResponse,
  QueryCoraOptions,
  QueryRequest,
  QueryResponse,
  QuizResponse,
  ReasoningStep,
  ReasoningStepDetails,
  ResponseMetadata,
  SSEDoneEvent,
  SSEErrorEvent,
  SSEEvent,
  SSEEventType,
  SSEReplaceEvent,
  SSEResultEvent,
  SSEStatusEvent,
  SSETokenEvent,
  StreamingCallbacks,
} from './cora/types';

export { buildAgentReasoning } from './cora/agentReasoning';
export { queryCora } from './cora/query';
export { queryCoraStream } from './cora/streaming';
export { checkHealth } from './cora/healthCheck';
