import type { AgentReasoningStep } from '@/types/reasoning';

/**
 * Thrown when the backend emits an SSE `error` event.
 *
 * Unlike transport or parse failures, `message` is authored server-side and is
 * safe to show to users verbatim (e.g. security blocks, "service initializing").
 * `errorId` correlates with backend logs. `reasoningSteps` carries the
 * sanitized partial trace when the failure happened mid-pipeline.
 */
export class CoraStreamError extends Error {
  readonly errorId: string;
  readonly reasoningSteps?: AgentReasoningStep[];

  constructor(errorId: string, message: string, reasoningSteps?: AgentReasoningStep[]) {
    super(message);
    this.name = 'CoraStreamError';
    this.errorId = errorId;
    this.reasoningSteps = reasoningSteps;
  }
}

/**
 * Thrown for transport-level query failures: a non-OK HTTP response or a
 * request that hit the client-side timeout.
 *
 * Carrying `status`/`kind` as typed fields lets the UI map errors to copy
 * without pattern-matching on message text.
 */
export class CoraApiError extends Error {
  readonly status?: number;
  readonly kind: 'http' | 'timeout';

  constructor(kind: 'http' | 'timeout', message: string, status?: number) {
    super(message);
    this.name = 'CoraApiError';
    this.kind = kind;
    this.status = status;
  }
}
