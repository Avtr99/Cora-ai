import { describe, it, expect } from 'vitest';
import {
  generateId,
  generateChatTitle,
  detectTopics,
} from './chatStore.utils';

describe('generateId', () => {
  it('generates unique IDs across multiple calls', () => {
    const ids = new Set<string>();
    for (let i = 0; i < 100; i++) {
      ids.add(generateId());
    }
    expect(ids.size).toBe(100);
  });

  it('returns a non-empty string', () => {
    const id = generateId();
    expect(typeof id).toBe('string');
    expect(id.length).toBeGreaterThan(0);
  });
});

describe('generateChatTitle', () => {
  it('returns short messages unchanged', () => {
    expect(generateChatTitle('Hello world')).toBe('Hello world');
  });

  it('truncates long messages to 30 chars with ellipsis', () => {
    const long = 'This is a very long message that exceeds thirty characters';
    expect(generateChatTitle(long)).toBe('This is a very long message th...');
  });

  it('handles exactly 30 characters without ellipsis', () => {
    const exact = 'a'.repeat(30);
    expect(generateChatTitle(exact)).toBe(exact);
  });

  it('handles empty string', () => {
    expect(generateChatTitle('')).toBe('');
  });
});

describe('detectTopics', () => {
  it('detects project-related keywords', () => {
    expect(detectTopics('Tell me about carbon projects')).toContain('project');
    expect(detectTopics('What methodologies are used?')).toContain('project');
    expect(detectTopics('Show me a case study')).toContain('project');
    expect(detectTopics('What about renewable energy?')).toContain('project');
  });

  it('does not detect project for unrelated words', () => {
    expect(detectTopics('projection mapping is cool')).not.toContain('project');
    expect(detectTopics('hello world')).not.toContain('project');
  });

  it('detects pricing with carbon context', () => {
    expect(detectTopics('What is the price of carbon credits?')).toContain('pricing');
    expect(detectTopics('How much do offsets cost?')).toContain('pricing');
    expect(detectTopics('Carbon credit pricing analysis')).toContain('pricing');
  });

  it('detects explicit pricing phrases without carbon context', () => {
    expect(detectTopics('What is the price per ton?')).toContain('pricing');
    expect(detectTopics('Show me $/t data')).toContain('pricing');
    expect(detectTopics('Credit price trends')).toContain('pricing');
  });

  it('does not detect pricing for generic price mentions without carbon context', () => {
    expect(detectTopics('What is the price of coffee?')).not.toContain('pricing');
    expect(detectTopics('Apple stock price')).not.toContain('pricing');
  });

  it('detects both topics when applicable', () => {
    const topics = detectTopics('What is the carbon price of REDD+ projects?');
    expect(topics).toContain('project');
    expect(topics).toContain('pricing');
  });

  it('returns empty array for irrelevant messages', () => {
    expect(detectTopics('Hello, how are you?')).toEqual([]);
    expect(detectTopics('The weather is nice today')).toEqual([]);
  });

  it('handles VM0048 methodology mentions', () => {
    expect(detectTopics('Tell me about VM0048')).toContain('project');
    expect(detectTopics('VM 0048 methodology')).toContain('project');
  });
});
