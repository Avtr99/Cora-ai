/**
 * Represents a step in the agent reasoning process.
 * Standalone type to avoid circular imports between store and service layers.
 */
export interface AgentReasoningStep {
  agentName: string;
  nodeName: string;
  messages?: string[];
  usedTools?: unknown[];
  sourceDocuments?: unknown[];
  artifacts?: unknown[];
  state?: object;
  nodeId?: string;
}
