import { describe, it, expect } from 'vitest';
import { decodeSourceLabel, parseCitationSources, preprocessContent } from './chatMessageCitations.utils';
import type { CitationSource } from './CitationBadges';

describe('decodeSourceLabel', () => {
  it('returns the label unchanged when no encoding is present', () => {
    expect(decodeSourceLabel('VM0047 ARR v1.0')).toBe('VM0047 ARR v1.0');
  });

  it('decodes %20 space characters', () => {
    expect(decodeSourceLabel('vm0047%20arr%20v1.0')).toBe('vm0047 arr v1.0');
  });

  it('decodes plus signs as spaces', () => {
    expect(decodeSourceLabel('vm0047+arr+v1.0')).toBe('vm0047 arr v1.0');
  });

  it('handles double-encoded labels', () => {
    expect(decodeSourceLabel('vm0047%2520arr%2520v1.0')).toBe('vm0047 arr v1.0');
  });

  it('handles triple-encoded labels', () => {
    expect(decodeSourceLabel('vm0047%252520arr%252520v1.0')).toBe('vm0047 arr v1.0');
  });

  it('returns the original label when decoding throws', () => {
    // % followed by invalid UTF-8 sequence would throw; using a lone % is enough
    expect(decodeSourceLabel('broken%')).toBe('broken%');
  });
});

describe('preprocessContent', () => {
  it('converts [cite_kb: N] to internal citation links', () => {
    const result = preprocessContent('Text [cite_kb: 1] more');
    expect(result).toBe('Text [kb](https://citation.internal/kb/1) more');
  });

  it('converts [Knowledge Base, cite: N, M] to internal links', () => {
    const result = preprocessContent('Text [Knowledge Base, cite: 1, 2] more');
    expect(result).toBe('Text [kb](https://citation.internal/kb/1,2) more');
  });

  it('converts [Web, cite: N] to internal links', () => {
    const result = preprocessContent('Text [Web, cite: 1] more');
    expect(result).toBe('Text [web](https://citation.internal/web/1) more');
  });

  it('converts legacy [source_1, source_2] to web internal links', () => {
    const result = preprocessContent('Text [source_1, source_2] more');
    expect(result).toBe('Text [web](https://citation.internal/web/1,2) more');
  });

  it('handles multiple citation markers', () => {
    const result = preprocessContent('A [cite_kb: 1] and B [Web, cite: 2]');
    expect(result).toBe(
      'A [kb](https://citation.internal/kb/1) and B [web](https://citation.internal/web/2)'
    );
  });

  it('removes numberless [Knowledge Base] markers instead of leaving a gap', () => {
    const result = preprocessContent('Text [Knowledge Base] more');
    expect(result).toBe('Text  more');
  });

  it('removes numberless [Web] markers instead of leaving a gap', () => {
    const result = preprocessContent('Text [Web] more');
    expect(result).toBe('Text  more');
  });
});

describe('parseCitationSources', () => {
  it('returns an empty array for empty input', () => {
    expect(parseCitationSources(null)).toEqual([]);
    expect(parseCitationSources(undefined)).toEqual([]);
    expect(parseCitationSources({})).toEqual([]);
  });

  it('parses citation details into typed sources', () => {
    const result = parseCitationSources({
      count: 2,
      sources: [],
      details: [
        {
          source_name: 'VM0047 ARR v1.0',
          source_type: 'knowledge_base',
          relevance_score: 0.9,
          page_number: 1,
          section: null,
          url: null,
          snippet: null,
        },
        {
          source_name: 'Example Article',
          source_type: 'web_search',
          relevance_score: 0.8,
          url: 'https://example.com/article',
          snippet: 'Some snippet',
        },
      ],
    });

    expect(result).toEqual([
      { label: 'VM0047 ARR v1.0', url: undefined, type: 'knowledge_base' },
      { label: 'example.com', url: 'https://example.com/article', type: 'web' },
    ] as CitationSource[]);
  });

  it('decodes URL-encoded KB source names in details', () => {
    const result = parseCitationSources({
      count: 1,
      sources: [],
      details: [
        {
          source_name: 'vm0047%20arr%20v1.0',
          source_type: 'knowledge_base',
          relevance_score: 0.9,
        },
      ],
    });

    expect(result).toEqual([
      { label: 'vm0047 arr v1.0', type: 'knowledge_base' },
    ] as CitationSource[]);
  });

  it('decodes URL-encoded source names from the fallback sources array', () => {
    const result = parseCitationSources({
      sources: ['vm0047%20arr%20v1.0', 'https://example.com/article'],
    });

    expect(result).toEqual([
      { label: 'vm0047 arr v1.0', type: 'knowledge_base' },
      { label: 'example.com', url: 'https://example.com/article', type: 'web' },
    ] as CitationSource[]);
  });

  it('deduplicates by URL and label', () => {
    const result = parseCitationSources({
      sources: ['https://example.com/article', 'https://example.com/article'],
    });

    expect(result).toHaveLength(1);
    expect(result[0]).toEqual({
      label: 'example.com',
      url: 'https://example.com/article',
      type: 'web',
    });
  });

  it('filters routing tokens from source arrays', () => {
    const result = parseCitationSources({
      sources: ['knowledge_base', 'web_search', 'hybrid', 'VM0047'],
    });

    expect(result).toEqual([{ label: 'VM0047', type: 'knowledge_base' }] as CitationSource[]);
  });

  it('decodes URL-encoded source names in the data\\ path fallback', () => {
    const result = parseCitationSources({
      sources: ['data\\vm0047%20arr%20v1.0'],
    });

    expect(result).toEqual([
      { label: 'vm0047 arr v1.0', type: 'knowledge_base' },
    ] as CitationSource[]);
  });

  it('decodes URL-encoded source names in the plain KB fallback', () => {
    const result = parseCitationSources({
      sources: ['vm0047%20arr%20v1.0'],
    });

    expect(result).toEqual([
      { label: 'vm0047 arr v1.0', type: 'knowledge_base' },
    ] as CitationSource[]);
  });
});
