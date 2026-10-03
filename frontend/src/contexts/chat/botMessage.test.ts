import { describe, it, expect } from 'vitest';
import { buildBotMessage, getEmptyKbAnswerText } from './botMessage';
import type { CoraResponse } from '@/services/cora/types';

const response = (overrides: Partial<CoraResponse> = {}): CoraResponse => ({
  text: 'Answer text',
  answerId: 'm1-answer',
  ...overrides,
});

describe('getEmptyKbAnswerText', () => {
  it('returns the empty-KB text when metadata.kb_empty is true', () => {
    const text = getEmptyKbAnswerText(response({ metadata: { route: 'knowledge_base', total_time_ms: 1, kb_empty: true } }));
    expect(text).toContain("couldn't find anything in the knowledge base");
  });

  it('returns null otherwise', () => {
    expect(getEmptyKbAnswerText(response())).toBeNull();
    expect(getEmptyKbAnswerText(response({ metadata: { route: 'knowledge_base', total_time_ms: 1 } }))).toBeNull();
  });
});

describe('buildBotMessage', () => {
  it('uses the server answerId as the message id', () => {
    const msg = buildBotMessage(response(), 'm1');
    expect(msg.id).toBe('m1-answer');
    expect(msg.replyToMessageId).toBe('m1');
    expect(msg.sender).toBe('bot');
    expect(msg.status).toBe('complete');
  });

  it('preserves citations, reasoning, metadata, quiz, prompts, and sources', () => {
    const msg = buildBotMessage(
      response({
        citations: { count: 1, sources: ['doc'], details: [] },
        agentReasoning: [{ agentName: 'a', nodeName: 'a', nodeId: 's0', messages: ['m'] }],
        metadata: { route: 'knowledge_base', total_time_ms: 12 },
        quiz: { question: 'Q', options: ['a', 'b'], correctIndex: 0, explanation: 'E' },
        suggestedPrompts: ['next?'],
        sources: ['knowledge_base'],
      }),
      'm1'
    );

    expect(msg.citations?.count).toBe(1);
    expect(msg.agentReasoning).toHaveLength(1);
    expect(msg.metadata?.route).toBe('knowledge_base');
    expect(msg.quiz?.question).toBe('Q');
    expect(msg.suggestedPrompts).toEqual(['next?']);
    expect(msg.sources).toEqual(['knowledge_base']);
  });

  it('replaces the text with the empty-KB message when kb_empty', () => {
    const msg = buildBotMessage(
      response({ text: '', metadata: { route: 'knowledge_base', total_time_ms: 1, kb_empty: true } }),
      'm1'
    );
    expect(msg.content).toContain("couldn't find anything in the knowledge base");
  });

  it('sets triggered recommendations only when non-empty', () => {
    const withRecs = buildBotMessage(response(), 'm1', {
      triggeredTopics: ['project'],
      triggeredRecommendationIds: ['project-1'],
    });
    expect(withRecs.triggeredRecommendations).toEqual(['project']);
    expect(withRecs.triggeredRecommendationIds).toEqual(['project-1']);

    const without = buildBotMessage(response(), 'm1');
    expect(without.triggeredRecommendations).toBeUndefined();
    expect(without.triggeredRecommendationIds).toBeUndefined();
  });

  it('honours an explicit timestamp', () => {
    const ts = new Date('2024-05-05T10:00:00Z');
    const msg = buildBotMessage(response(), 'm1', { timestamp: ts });
    expect(msg.timestamp).toBe(ts);
  });
});
