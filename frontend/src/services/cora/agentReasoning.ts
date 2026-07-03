import { AgentReasoningStep, QueryResponse } from './types';

const truncateText = (value: string, max: number = 120): string => {
  const trimmed = value.trim();
  if (!trimmed) return '';
  return trimmed.length > max ? `${trimmed.substring(0, max).trim()}…` : trimmed;
};

export function buildAgentReasoning(response: QueryResponse): AgentReasoningStep[] {
  if (!Array.isArray(response.reasoning_steps) || response.reasoning_steps.length === 0) {
    return [];
  }

  const results: (AgentReasoningStep | null)[] = response.reasoning_steps.map((step, index) => {
    if (!step) {
      return null;
    }

    const details = step.details ?? {};
    const name = (step.name || '').toLowerCase();
    const status = (step.status || '').toLowerCase();
    const messages: string[] = [];

    if (name.includes('rewrite') || name.includes('rewrit') || name.includes('clarif')) {
      // Show a clean message instead of raw rewritten_query with metadata
      if (details.rewritten_query) {
        // Strip metadata parameters like methodology_code="..." registry="..."
        const cleanQuery = typeof details.rewritten_query === 'string'
          ? details.rewritten_query.replace(/\s+\w+="[^"]*"/g, '')
          : '';
        if (cleanQuery) {
          messages.push(`Refined: "${truncateText(cleanQuery, 100)}"`);
        } else {
          messages.push('Query refined for better search');
        }
      }
    } else if (name.includes('rout')) {
      if (details.route === 'knowledge_base' || details.route === 'vector_store') {
        messages.push('Checking knowledge base for information');
      } else if (details.route === 'web_search' || details.route === 'web') {
        messages.push('Checking web sources for information');
      } else if (details.route) {
        const routeStr = String(details.route);
        messages.push(`Information found via ${routeStr.replace(/_/g, ' ')}`);
      }
    } else if (name.includes('retriev') || name.includes('search') || name.includes('kb')) {
      const count = details.documents_retrieved ?? details.results_count ?? details.count;
      if (typeof count === 'number') {
        messages.push(`Found ${count} relevant source(s)`);
      }
      // Only show snippets/highlights if we actually found documents (count > 0)
      // and filter out generic placeholder messages
      const isEmptyResult = typeof count === 'number' && count === 0;
      if (!isEmptyResult) {
        const possibleSnippets = details.highlights ?? details.snippets ?? details.results ?? details.documents ?? details.sources;
        if (Array.isArray(possibleSnippets)) {
          possibleSnippets
            .filter((h): h is string => typeof h === 'string' && h.trim().length > 0)
            .filter(h => !/^found \d+ relevant/i.test(h))
            .filter(h => !/^retrieved supporting information/i.test(h)) // Filter out generic placeholder
            .slice(0, 3)
            .forEach(h => {
              const snippet = truncateText(h, 100);
              if (snippet) {
                messages.push(snippet);
              }
            });
        }
      }
    } else if (
      (name.includes('answer') || name.includes('generat') || name.includes('draft')) &&
      !name.includes('validat') &&
      !name.includes('quality') &&
      !name.includes('check')
    ) {
      const ANSWER_PREVIEW_MAX_CHARS = 220;
      if (details.answer_preview && typeof details.answer_preview === 'string') {
        const snippet = truncateText(details.answer_preview, ANSWER_PREVIEW_MAX_CHARS);
        if (snippet) {
          messages.push(snippet);
        }
      } else if (details.summary && typeof details.summary === 'string' && !/^generated answer from/i.test(details.summary.trim())) {
        const snippet = truncateText(details.summary, ANSWER_PREVIEW_MAX_CHARS);
        if (snippet) {
          messages.push(snippet);
        }
      } else if (response.answer && response.answer.trim()) {
        const snippet = truncateText(response.answer, ANSWER_PREVIEW_MAX_CHARS);
        if (snippet) {
          messages.push(snippet);
        }
      } else {
        messages.push('Generated final answer');
      }
    } else if (name.includes('validat') || name.includes('quality') || name.includes('check')) {
      if (status === 'skipped') {
        return null;
      }
      const summary = typeof details.summary === 'string' ? details.summary.toLowerCase() : '';
      if (summary.includes('skip') || summary.includes('skipped')) {
        return null;
      }
      messages.push((typeof details.summary === 'string' && details.summary) || 'Answer grounded in facts');
    } else {
      if (details.summary && typeof details.summary === 'string') {
        messages.push(details.summary);
      }
    }

    if (!messages.length) return null;

    return {
      agentName: step.name,
      nodeName: step.name,
      messages,
      nodeId: `step-${index}`,
    };
  });

  return results.filter((s): s is AgentReasoningStep => s !== null);
}
