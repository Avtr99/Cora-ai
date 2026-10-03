import { AgentReasoningStep } from '@/types/reasoning';

export type { AgentReasoningStep };

export interface QueryRequest {
  text: string;
  conversation_id?: string;
  message_id?: string;
  session_id?: string;
  include_debug?: boolean;
}

export interface CitationDetail {
  source_name: string;
  source_type: 'knowledge_base' | 'web_search';
  relevance_score: number;
  page_number: number | null;
  section: string | null;
  url: string | null;
  snippet: string | null;
  // The prompt position (N in [cite_kb: N] / [Web, cite: N]). Absent for
  // marker-less citations (e.g. structured datasets).
  index?: number;
  // Which marker namespace `index` belongs to. A web result can carry
  // source_type "knowledge_base" (file-like display classification) while
  // still being numbered among web results.
  marker_type?: 'knowledge_base' | 'web';
  // Identity of the underlying document (doc store ID for KB chunks, URL
  // for web results); chunks sharing it merge into one badge.
  document_key?: string;
  // VCM metadata surfaced from the source document (registry, publisher,
  // version_number, document_id, methodology_codes, etc.). Present for KB
  // citations when the source carries VCM metadata; absent for web citations.
  metadata?: Record<string, unknown> | null;
}

export interface CitationResponse {
  count: number;
  sources: string[];
  details: CitationDetail[];
}

export interface ReasoningStepDetails {
  original_query?: string;
  rewritten_query?: string;
  route?: string;
  reason?: string;
  title?: string;
  summary?: string;
  highlights?: string[];
  snippets?: string[];
  results?: string[];
  documents?: string[];
  documents_retrieved?: number;
  results_count?: number;
  count?: number;
  source?: string;
  sources?: string[];
  corrections?: string[];
  answer_preview?: string;
}

export interface ReasoningStep {
  name: string;
  status: 'completed' | 'in_progress' | 'skipped';
  duration_ms: number;
  details: Record<string, unknown>;
}

export interface ResponseMetadata {
  route: 'knowledge_base' | 'web_search' | 'hybrid' | 'conversational';
  timing_breakdown?: {
    rewrite_ms?: number;
    routing_ms?: number;
    retrieval_ms?: number;
    web_search_ms?: number;
    generation_ms?: number;
    total_time_ms: number;
  };
  timeout_reason?: string | null;
  total_time_ms: number;
  // True when the KB route retrieved zero documents and web search was disabled.
  kb_empty?: boolean;
}

export interface QuizResponse {
  question: string;
  options: string[];
  correctIndex: number;
  explanation: string;
}

export interface QueryResponse {
  answer: string;
  confidence: number;
  sources: string[];
  conversation_id: string;
  message_id?: string;
  answer_id?: string;
  timestamp: string;
  citations: CitationResponse | null;
  reasoning_steps: ReasoningStep[] | null;
  metadata?: ResponseMetadata;
  quiz: QuizResponse | null;
  suggested_prompts?: string[];
}

export interface CoraResponse {
  text: string;
  confidence?: number;
  sources?: string[];
  conversationId?: string;
  messageId?: string;
  answerId?: string;
  timestamp?: string;
  agentReasoning?: AgentReasoningStep[];
  citations?: CitationResponse;
  metadata?: ResponseMetadata;
  quiz?: QuizResponse;
  suggestedPrompts?: string[];
}

export interface QueryCoraOptions {
  signal?: AbortSignal;
}

export type SSEEventType = 'status' | 'token' | 'replace' | 'result' | 'done' | 'error';

export interface SSEStatusEvent {
  event: 'status';
  /** @example 'accepted', 'processing' */
  status?: string;
  message?: string;
  stage?: string;
  progress?: number;
}

export interface SSEResultEvent {
  event: 'result';
  payload: QueryResponse;
}

export interface SSEDoneEvent {
  event: 'done';
}

export interface SSETokenEvent {
  event: 'token';
  chunk: string;
}

export interface SSEReplaceEvent {
  event: 'replace';
}

export interface SSEErrorEvent {
  event: 'error';
  error_id: string;
  message: string;
}

export type SSEEvent =
  | SSEStatusEvent
  | SSETokenEvent
  | SSEReplaceEvent
  | SSEResultEvent
  | SSEDoneEvent
  | SSEErrorEvent;

export interface StreamingCallbacks {
  onStatus?: (event: SSEStatusEvent) => void;
  onToken?: (chunk: string) => void;
  onReplace?: () => void;
  onResult?: (response: CoraResponse) => void;
  onError?: (errorId: string, message: string) => void;
  onDone?: () => void;
}
