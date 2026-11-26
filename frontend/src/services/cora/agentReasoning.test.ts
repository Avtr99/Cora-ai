import { describe, expect, it } from 'vitest';
import { buildAgentReasoning } from './agentReasoning';
import type { ReasoningStep } from './types';

function buildStep(step: Omit<ReasoningStep, 'duration_ms'>) {
  return buildAgentReasoning({ reasoning_steps: [{ duration_ms: 0, ...step }] })[0];
}

describe('buildAgentReasoning', () => {
  it('keeps retrieval excerpts from saved turns written before details.sources', () => {
    const step = buildStep({
      name: 'Knowledge Base Retrieval',
      status: 'completed',
      details: {
        documents_retrieved: 1,
        highlights: ['Found 1 relevant document(s) from knowledge base', 'VM0048: A forest methodology.'],
      },
    });

    expect(step.sources).toEqual(['VM0048: A forest methodology.']);
  });

  it('does not list a placeholder as a source on a failed search', () => {
    const step = buildStep({
      name: 'Web Search',
      status: 'fallback',
      details: { sources: ['Retrieved supporting information for answer generation'] },
    });

    expect(step.status).toBe('fallback');
    expect(step.sources).toBeUndefined();
  });

  it('shows the outcome of a web supplement rather than the action it attempted', () => {
    const summary = 'Kept the knowledge base answer.';
    const step = buildStep({
      name: 'Web Supplementation',
      status: 'fallback',
      details: { summary },
    });

    expect(step.status).toBe('fallback');
    expect(step.messages).toEqual([summary]);
  });
});
