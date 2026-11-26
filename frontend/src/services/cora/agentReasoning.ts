import { AgentReasoningStep, QueryResponse } from './types';

const STEP_STATES: Record<string, AgentReasoningStep['status']> = {
  started: 'running', running: 'running', in_progress: 'running', completed: 'complete',
  failed: 'error', error: 'error', cancelled: 'cancelled',
  skipped: 'skipped', cached: 'cached', fallback: 'fallback',
};

/**
 * Name → kind fallback for responses stored before details.kind existed.
 * This is one of exactly two legacy normalizers — the other is
 * upgrade_reasoning_steps at the backend cache read (src/utils/cache.py).
 * This one is required because chat_turns history rows bypass that cache
 * path. Do not add a third normalization point.
 */
const KIND_BY_NAME: Record<string, string> = {
  'query rewriting': 'understand',
  'query routing': 'route',
  'knowledge base retrieval': 'search_kb',
  'hybrid retrieval': 'search_kb',
  'web search': 'search_web',
  'web supplementation': 'search_web',
  'fallback decision': 'fallback',
  'answer generation': 'compose',
  'answer synthesis': 'compose',
  'answer validation': 'verify',
};

const GENERIC_DETAILS = new Set([
  'Prepared the query for the next steps',
  'Collected evidence to answer the question',
  'Composed a response based on retrieved information',
  'Processing step completed',
  'Step finished',
]);

/** details.source / details.method on compose steps → display phrase. */
const COMPOSE_SOURCE_LABELS: Record<string, string> = {
  knowledge_base: 'the knowledge base',
  kb_fallback: 'the knowledge base',
  web_answer: 'web results',
  web_only: 'web results',
};

/** Strip metadata parameters like methodology_code="..." registry="..." */
const cleanRewrittenQuery = (value: string): string =>
  value.replace(/\s+\w+="[^"]*"/g, '').trim();

const str = (v: unknown): string => (typeof v === 'string' ? v.trim() : '');

const num = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

/** Document ID surfaced in rewrite_info filters when the router matched one. */
const documentIdFromResponse = (response: Pick<QueryResponse, 'metadata'>): string => {
  const filters = response.metadata?.rewrite_info?.filters;
  return str(filters?.document_id) || str(filters?.registry_document_id);
};

const routeMessage = (
  details: Record<string, unknown>,
  response: Pick<QueryResponse, 'metadata'>,
): string => {
  const route = str(details.route).toLowerCase();
  const reason = str(details.reason);
  const docId = reason === 'Document ID detected' ? documentIdFromResponse(response) : '';
  const checking =
    route === 'knowledge_base' || route === 'vector_store'
      ? 'Checking the knowledge base'
      : route === 'web_search' || route === 'web'
        ? 'Checking the web'
        : route === 'hybrid'
          ? 'Checking the knowledge base and web'
          : '';
  if (docId && checking) return `Matched the document ${docId}: ${checking.toLowerCase()}`;
  if (checking) return checking;
  return str(details.summary) || 'Finding the best source';
};

const fallbackMessage = (details: Record<string, unknown>): string => {
  const reason = str(details.reason);
  if (/cach/i.test(reason)) return 'No knowledge base results. Using a recent answer';
  if (/web/i.test(reason)) return 'The knowledge base did not have enough. Checking the web';
  return reason || 'Adjusted the retrieval strategy';
};

const verifyMessage = (details: Record<string, unknown>): string => {
  const grounded = details.is_grounded;
  if (grounded === true) return 'Answer grounded in facts';
  if (grounded === false) return 'Some claims are not fully supported by the sources';
  return str(details.summary) || 'Answer grounded in facts';
};

export function buildAgentReasoning(
  response: Pick<QueryResponse, 'reasoning_steps' | 'metadata'>,
): AgentReasoningStep[] {
  if (!Array.isArray(response.reasoning_steps) || response.reasoning_steps.length === 0) {
    return [];
  }

  const results: (AgentReasoningStep | null)[] = response.reasoning_steps.map((step, index) => {
    if (!step) return null;

    const details = (step.details ?? {}) as Record<string, unknown>;
    const statusRaw = (step.status || '').toLowerCase();
    const status = STEP_STATES[statusRaw];
    const name = (step.name || '').toLowerCase();
    const kind = str(details.kind) || KIND_BY_NAME[name] || 'step';
    const title = str(details.title) || step.name || 'Processing';

    // Skipped steps carry no user value — hide them entirely.
    if (status === 'skipped') return null;

    const messages: string[] = [];
    let sources: string[] = [];
    const summary = str(details.summary);

    if (kind === 'understand') {
      const refined = cleanRewrittenQuery(str(details.rewritten_query));
      if (refined) {
        messages.push(`Refined: "${refined}"`);
      } else if (summary && !GENERIC_DETAILS.has(summary)) {
        messages.push(summary);
      }
    } else if (kind === 'route') {
      messages.push(routeMessage(details, response));
    } else if (kind === 'search_kb' || kind === 'search_web') {
      const count =
        num(details.documents_retrieved) ?? num(details.results_count) ?? num(details.sources_found) ?? num(details.count);
      if (status === 'fallback' || status === 'error') {
        messages.push(
          summary && !GENERIC_DETAILS.has(summary)
            ? summary
            : 'The search did not return a usable answer.',
        );
      } else if (name.includes('supplement')) {
        messages.push('The knowledge base did not have enough. Checking the web');
      } else if (count !== null) {
        messages.push(`Found ${count} relevant source${count === 1 ? '' : 's'}`);
      } else if (summary && !GENERIC_DETAILS.has(summary)) {
        messages.push(summary);
      }
      const excerpts = details.sources ?? details.highlights;
      if (Array.isArray(excerpts)) {
        sources = excerpts.map(str).filter(
          (source) => source && !/^(found \d+ relevant|retrieved supporting information)/i.test(source),
        );
      }
    } else if (kind === 'fallback') {
      messages.push(fallbackMessage(details));
    } else if (kind === 'compose') {
      const source = str(details.source) || str(details.method);
      messages.push(
        status === 'error'
          ? 'Answer generation failed'
          : `Generated answer from ${COMPOSE_SOURCE_LABELS[source] ?? 'the retrieved sources'}`,
      );
    } else if (kind === 'verify') {
      messages.push(verifyMessage(details));
    } else if (summary && !GENERIC_DETAILS.has(summary)) {
      messages.push(summary);
    }

    // Drop empty generic steps; keep every named kind and any step carrying a
    // non-complete status such as failed.
    const hasContent = messages.length > 0 || sources.length > 0;
    const isMeaningful = kind !== 'step' || (status !== undefined && status !== 'complete');
    if (!hasContent && !isMeaningful) return null;

    return {
      agentName: title,
      nodeName: step.name,
      kind,
      status,
      messages,
      sources: sources.length ? sources : undefined,
      nodeId: `step-${index}`,
    };
  });

  return results.filter((s): s is AgentReasoningStep => s !== null);
}
