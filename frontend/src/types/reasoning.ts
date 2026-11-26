/**
 * Represents a step in the agent reasoning process.
 * Standalone type to avoid circular imports between store and service layers.
 */
export interface AgentReasoningStep {
  agentName: string;
  nodeName: string;
  /** Backend-emitted step kind (understand|route|search_kb|search_web|compose|verify|fallback|step) for icon/message mapping. */
  kind?: string;
  status?: 'running' | 'complete' | 'error' | 'cancelled' | 'skipped' | 'cached' | 'fallback';
  messages?: string[];
  /** Clean source display names listed under a retrieval step. */
  sources?: string[];
  usedTools?: unknown[];
  sourceDocuments?: unknown[];
  artifacts?: unknown[];
  state?: object;
  nodeId?: string;
}
