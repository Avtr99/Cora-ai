import { describe, it, expect } from 'vitest';
import {
  buildCitationNumberMap,
  markerNumbersToGlobal,
  decodeSourceLabel,
  parseCitationSources,
  preprocessContent,
} from './chatMessageCitations.utils';
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

  it('preserves a lone broken %', () => {
    expect(decodeSourceLabel('broken%')).toBe('broken%');
  });

  it('decodes %20 even when the string also contains a broken %', () => {
    // A single malformed % used to abort decodeURIComponent and return the
    // whole raw string, which is why %20 stayed visible in the UI.
    expect(decodeSourceLabel('vm0048%20reducing%')).toBe('vm0048 reducing%');
    expect(decodeSourceLabel('vm0048%20reducing%20emissions%20v1.0-1-1.pdf%')).toBe(
      'vm0048 reducing emissions v1.0-1-1.pdf%'
    );
  });

  it('decodes %20 in the VM0048 long filename with a broken trailing %', () => {
    const result = decodeSourceLabel(
      'vm0048%20reducing%20emissions%20from%20deforestation%20and%20forest%20degradation%20v1.0-1-1.pdf%'
    );
    expect(result).toBe(
      'vm0048 reducing emissions from deforestation and forest degradation v1.0-1-1.pdf%'
    );
    expect(result).not.toContain('%20');
  });

  it('decodes double-encoded values even with a broken %', () => {
    expect(decodeSourceLabel('vm0048%2520reducing%')).toBe('vm0048 reducing%');
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

  it('converts consecutive citation markers without whitespace', () => {
    const result = preprocessContent('A [cite_kb: 1][Web, cite: 2]');
    expect(result).toBe(
      'A [kb](https://citation.internal/kb/1)[web](https://citation.internal/web/2)'
    );
  });

  it('converts consecutive legacy source markers', () => {
    const result = preprocessContent('A [source_1][source_2]');
    expect(result).toBe(
      'A [web](https://citation.internal/web/1)[web](https://citation.internal/web/2)'
    );
  });

  it('removes empty bracketed citation markers instead of leaving a gap', () => {
    expect(preprocessContent('Text [cite_kb: ] more')).toBe('Text  more');
    expect(preprocessContent('Text [Knowledge Base, cite: ] more')).toBe('Text  more');
    expect(preprocessContent('Text [Web, cite: ] more')).toBe('Text  more');
  });

  it('leaves plain empty brackets unchanged', () => {
    expect(preprocessContent('Text [] more')).toBe('Text [] more');
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

  it('decodes the VM0048 citation filename returned by KB retrieval', () => {
    const result = parseCitationSources({
      details: [{
        source_name: 'vm0048%20reducing%20emissions%20from%20deforestation%20and%20forest%20degradation%20v1.0-1-1.pdf',
        source_type: 'knowledge_base',
      }],
    });

    expect(result[0]).toEqual({
      label: 'vm0048 reducing emissions from deforestation and forest degradation v1.0-1-1',
      type: 'knowledge_base',
    });
    expect(result[0].label).not.toContain('%20');
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

  it('keeps two indexed details without document_key as separate badges', () => {
    const result = parseCitationSources({
      details: [
        {
          source_name: 'VM0007 Methodology',
          source_type: 'knowledge_base',
          index: 1,
          marker_type: 'knowledge_base',
        },
        {
          source_name: 'VM0007 Methodology',
          source_type: 'knowledge_base',
          index: 2,
          marker_type: 'knowledge_base',
        },
      ],
    });

    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({
      label: 'VM0007 Methodology',
      type: 'knowledge_base',
      indices: [1],
      markerType: 'kb',
    });
    expect(result[1]).toEqual({
      label: 'VM0007 Methodology',
      type: 'knowledge_base',
      indices: [2],
      markerType: 'kb',
    });
  });

  it('merges indexed details that share a document_key into one badge', () => {
    const result = parseCitationSources({
      details: [
        {
          source_name: 'VM0007 Methodology',
          source_type: 'knowledge_base',
          index: 1,
          marker_type: 'knowledge_base',
          document_key: 'key-a',
          page_number: 2,
        },
        {
          source_name: 'VM0042 Standard',
          source_type: 'knowledge_base',
          index: 2,
          marker_type: 'knowledge_base',
          document_key: 'key-b',
        },
        {
          source_name: 'VM0007 Methodology',
          source_type: 'knowledge_base',
          index: 3,
          marker_type: 'knowledge_base',
          document_key: 'key-a',
          page_number: 5,
        },
      ],
    });

    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({
      label: 'VM0007 Methodology',
      type: 'knowledge_base',
      indices: [1, 3],
      pages: [2, 5],
      markerType: 'kb',
    });
    expect(result[1]).toEqual({
      label: 'VM0042 Standard',
      type: 'knowledge_base',
      indices: [2],
      markerType: 'kb',
    });

    const map = buildCitationNumberMap(result);
    expect(map['kb:1']).toBe(1);
    expect(map['kb:3']).toBe(1);
    expect(map['kb:2']).toBe(2);
  });

  it('does not merge the same document_key across kb and web namespaces', () => {
    const result = parseCitationSources({
      details: [
        {
          source_name: 'Shared Doc',
          source_type: 'knowledge_base',
          index: 1,
          marker_type: 'knowledge_base',
          document_key: 'shared',
        },
        {
          source_name: 'Example Article',
          source_type: 'web',
          url: 'https://example.com/a',
          index: 1,
          marker_type: 'web',
          document_key: 'shared',
        },
      ],
    });

    expect(result).toHaveLength(2);
    expect(result[0].markerType).toBe('kb');
    expect(result[1].markerType).toBe('web');
  });

  it('still deduplicates identical unindexed details', () => {
    const result = parseCitationSources({
      details: [
        { source_name: 'VM0007', source_type: 'knowledge_base' },
        { source_name: 'VM0007', source_type: 'knowledge_base' },
      ],
    });

    expect(result).toHaveLength(1);
  });
});

describe('buildCitationNumberMap', () => {
  it('maps kb:N marker keys to global source positions using the backend index', () => {
    const sources: CitationSource[] = [
      { label: 'Doc A', type: 'knowledge_base', indices: [1], markerType: 'kb' },
      { label: 'Doc B', type: 'knowledge_base', indices: [2], markerType: 'kb' },
      { label: 'example.com', url: 'https://example.com', type: 'web', indices: [1], markerType: 'web' },
    ];

    const map = buildCitationNumberMap(sources);

    expect(map['kb:1']).toBe(1);
    expect(map['kb:2']).toBe(2);
    expect(map['web:1']).toBe(3);
  });

  it('handles sparse indices — the prompt index, not the list position, is the key', () => {
    // Only chunk 7 was cited and shown; [cite_kb: 7] must still resolve.
    const sources: CitationSource[] = [
      { label: 'Doc G', type: 'knowledge_base', indices: [7], markerType: 'kb' },
    ];

    const map = buildCitationNumberMap(sources);

    expect(map['kb:7']).toBe(1);
    expect(map['kb:1']).toBeUndefined();
  });

  it('maps legacy unindexed payloads positionally per type', () => {
    const sources: CitationSource[] = [
      { label: 'Doc A', type: 'knowledge_base' },
      { label: 'Doc B', type: 'knowledge_base' },
      { label: 'example.com', url: 'https://example.com', type: 'web' },
    ];

    const map = buildCitationNumberMap(sources);

    expect(map['kb:1']).toBe(1);
    expect(map['kb:2']).toBe(2);
    expect(map['web:1']).toBe(3);
  });
});

describe('markerNumbersToGlobal', () => {
  const map = buildCitationNumberMap([
    // Ten chunks of one document merged into a single badge at position 1.
    { label: 'Doc A', type: 'knowledge_base', indices: [1, 2, 3, 4, 5], markerType: 'kb' },
    { label: 'Doc B', type: 'knowledge_base', indices: [6], markerType: 'kb' },
    { label: 'example.com', url: 'https://example.com', type: 'web', indices: [1], markerType: 'web' },
  ]);

  it('collapses a marker list that resolves to one merged badge', () => {
    // Model emitted [cite_kb: 1, 2, 3, 4, 5] — all the same document.
    expect(markerNumbersToGlobal('kb', [1, 2, 3, 4, 5], map)).toEqual([1]);
  });

  it('keeps distinct badge positions in order and drops unmapped numbers', () => {
    expect(markerNumbersToGlobal('kb', [1, 6, 99], map)).toEqual([1, 2]);
    expect(markerNumbersToGlobal('web', [1], map)).toEqual([3]);
  });

  it('returns empty when nothing maps', () => {
    expect(markerNumbersToGlobal('kb', [9], map)).toEqual([]);
    expect(markerNumbersToGlobal('kb', [1], undefined)).toEqual([]);
  });
});
