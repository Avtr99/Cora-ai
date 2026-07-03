import { AgentReasoningStep } from '@/types/reasoning';

export type { AgentReasoningStep };

export interface QueryRequest {
  text: string;
  conversation_id?: string;
  session_id?: string;
  history?: ChatHistoryMessage[];
  history_signature?: string; // HMAC signature for history verification
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
  // History verification warnings
  history_verification_failed?: boolean;
  history_items_dropped?: number;
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
  timestamp: string;
  citations: CitationResponse | null;
  reasoning_steps: ReasoningStep[] | null;
  metadata?: ResponseMetadata;
  quiz: QuizResponse | null;
  history_signature?: string; // HMAC signature for history verification
  suggested_prompts?: string[];
}

export interface CoraResponse {
  text: string;
  confidence?: number;
  sources?: string[];
  conversationId?: string;
  timestamp?: string;
  agentReasoning?: AgentReasoningStep[];
  citations?: CitationResponse;
  metadata?: ResponseMetadata;
  quiz?: QuizResponse;
  historySignature?: string; // HMAC signature for history verification
  suggestedPrompts?: string[];
}

export interface ChatHistoryMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
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
