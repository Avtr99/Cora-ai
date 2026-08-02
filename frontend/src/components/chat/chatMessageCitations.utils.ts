import { CitationSource } from './CitationBadges';
import { sanitizeUrl } from '@/lib/security';
import type { CitationResponse } from '@/services/cora/types';

const INLINE_CITATION_REGEX = /\[(?:(Knowledge Base|Web)(?:,\s*cite:\s*([\d,\s]+))?|cite_(kb|web):\s*([\d,\s]+)|((?:source_\d+(?:,\s*)?)+))\]/g;
const ROUTING_SOURCE_TOKENS = new Set(['knowledge_base', 'web_search', 'hybrid', 'error_fallback']);
export const CITATION_INTERNAL_URL = 'https://citation.internal/';

const MAX_DECODE_PASSES = 8;

/** Encode a Unicode code point as UTF-8 bytes. */
function codePointToUtf8(point: number): number[] {
  if (point <= 0x7f) return [point];
  if (point <= 0x7ff) return [0xc0 | (point >> 6), 0x80 | (point & 0x3f)];
  if (point <= 0xffff) {
    return [
      0xe0 | (point >> 12),
      0x80 | ((point >> 6) & 0x3f),
      0x80 | (point & 0x3f),
    ];
  }
  return [
    0xf0 | (point >> 18),
    0x80 | ((point >> 12) & 0x3f),
    0x80 | ((point >> 6) & 0x3f),
    0x80 | (point & 0x3f),
  ];
}

/**
 * Percent-decode a string, leaving invalid/broken % sequences as literals.
 * Works byte-by-byte so a single malformed % does not abort decoding of the
 * rest of the label (e.g. `vm0048%20reducing%` -> `vm0048 reducing%`).
 */
function safePercentDecode(input: string): string {
  const bytes: number[] = [];
  let i = 0;
  while (i < input.length) {
    if (input[i] === '%' && i + 2 < input.length) {
      const hex = input.slice(i + 1, i + 3);
      if (/^[0-9A-Fa-f]{2}$/.test(hex)) {
        bytes.push(parseInt(hex, 16));
        i += 3;
        continue;
      }
    }

    const code = input.charCodeAt(i);
    // Handle UTF-16 surrogate pairs so characters outside the BMP round-trip.
    if (code >= 0xd800 && code <= 0xdbff && i + 1 < input.length) {
      const low = input.charCodeAt(i + 1);
      if (low >= 0xdc00 && low <= 0xdfff) {
        const point = 0x10000 + ((code - 0xd800) << 10) + (low - 0xdc00);
        bytes.push(...codePointToUtf8(point));
        i += 2;
        continue;
      }
    }

    bytes.push(...codePointToUtf8(code));
    i += 1;
  }

  return new TextDecoder().decode(new Uint8Array(bytes));
}

/**
 * Decode URL-encoded source names defensively (e.g. vm0047%20arr%20v1.0).
 * Handles %20, +, double/triple encoding, and malformed % sequences that
 * would make decodeURIComponent throw.
 */
export function decodeSourceLabel(label: string): string {
  if (!label || (!label.includes('%') && !label.includes('+'))) return label;
  let decoded = label.replace(/\+/g, ' ');
  for (let pass = 0; pass < MAX_DECODE_PASSES; pass++) {
    const next = safePercentDecode(decoded);
    if (next === decoded) break;
    decoded = next;
  }
  return decoded;
}

function cleanKbLabel(label: string): string {
  return decodeSourceLabel(label.replace(/^data[\\/]/, '').trim()).replace(/\.(?:pdf|docx?|txt|md|html?)$/i, '');
}

interface CitationDetailShape {
  source_name?: unknown;
  source_type?: unknown;
  url?: unknown;
  snippet?: unknown;
}

export function preprocessContent(content: string): string {
  return content.replace(INLINE_CITATION_REGEX, (match, ...args) => {
    const [p1, p2, p3, p4, p5] = args;

    let type = 'kb';
    let nums = '';

    if (p1) {
      type = p1.toLowerCase() === 'web' ? 'web' : 'kb';
      nums = p2;
    } else if (p3) {
      type = p3;
      nums = p4;
    } else if (p5) {
      // Web search legacy format: [source_1, source_2] -> [cite_web: 1, 2]
      type = 'web';
      nums = p5.match(/source_(\d+)/g)?.map((s: string) => s.replace('source_', '')).join(',') || '';
    }

    const cleanNums = nums ? nums.split(',').map(s => s.trim()).filter(Boolean).join(',') : '';

    // Numberless markers (e.g. bare "[Knowledge Base]" or "[Web]") carry no
    // source reference. Remove them from the text instead of leaving a gap.
    if (!cleanNums) {
      return '';
    }

    return `[${type}](${CITATION_INTERNAL_URL}${type}/${cleanNums})`;
  });
}

export function parseCitationSources(citations: CitationResponse | Record<string, unknown> | unknown[] | null | undefined): CitationSource[] {
  if (!citations) return [];

  const links: CitationSource[] = [];
  const seen = new Set<string>();

  const isRoutingToken = (value: string): boolean => ROUTING_SOURCE_TOKENS.has(value.trim().toLowerCase());

  const toStringValue = (value: unknown): string => (typeof value === 'string' ? value.trim() : '');

  // Debug utility - single point of control for logging
  const debug = import.meta.env.DEV ? console.log.bind(console, '[parseCitationSources]') : () => {};

const FILE_EXT_BLACKLIST = new Set([
    'txt', 'md', 'json', 'csv', 'pdf', 'jpg', 'jpeg', 'png', 'gif', 'svg', 'webp',
    'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'zip', 'tar', 'gz', 'bz2', 'rar', '7z',
    'mp3', 'mp4', 'avi', 'mov', 'wmv', 'flv', 'wav', 'ogg', 'webm', 'exe', 'dmg',
    'pkg', 'deb', 'rpm', 'apk', 'ipa', 'py', 'js', 'ts', 'tsx', 'jsx', 'java', 'cpp',
    'c', 'h', 'hpp', 'go', 'rs', 'rb', 'php', 'swift', 'kt', 'scala', 'r', 'lua',
    'sh', 'bash', 'ps1', 'sql', 'yaml', 'yml', 'toml', 'ini', 'cfg', 'conf', 'log',
  ]);

  const isWebSource = (str: string): boolean => {
    const lower = str.toLowerCase();
    if (lower.startsWith('http://') || lower.startsWith('https://') || lower.startsWith('(http')) {
      return true;
    }
    const match = /^[a-z0-9][a-z0-9-]*\.([a-z]{2,})/i.exec(lower);
    if (!match) return false;
    return !FILE_EXT_BLACKLIST.has(match[1]);
  };

  const extractDomain = (str: string): string => {
    try {
      const decodedStr = decodeSourceLabel(str).replace(/^\(/, '').replace(/\)$/, '').trim();
      const url = decodedStr.startsWith('http') ? new URL(decodedStr) : new URL(`https://${decodedStr}`);
      return url.hostname.replace(/^www\./, '');
    } catch {
      return str;
    }
  };

  const extractFirstUrl = (text: string): string | undefined => {
    const matches = text.match(/https?:\/\/[^\s"'>]+/gi);
    if (!matches) return undefined;
    for (const raw of matches) {
      let candidate = raw.replace(/[.,;:!?]+$/, '');
      let openCount = (candidate.match(/\(/g) || []).length;
      let closeCount = (candidate.match(/\)/g) || []).length;
      while (closeCount > openCount && candidate.endsWith(')')) {
        candidate = candidate.slice(0, -1);
        openCount = (candidate.match(/\(/g) || []).length;
        closeCount = (candidate.match(/\)/g) || []).length;
      }
      const safe = sanitizeUrl(candidate);
      if (safe) {
        return safe;
      }
    }
    return undefined;
  };

  const getDomainLabel = (value: string): string => {
    const domain = extractDomain(value);
    return domain || value;
  };

  const _citations = citations as Record<string, unknown>;
  if (Array.isArray(_citations.details)) {
    debug('Processing details:', (_citations.details as unknown[]).length, 'items');
    for (const detail of _citations.details as unknown[]) {
      if (typeof detail !== 'object' || detail === null) continue;
      const d = detail as CitationDetailShape;

      // Backend now automatically URL-decodes, strips file extensions, and
      // removes search-engine prefixes (e.g. [PDF]). We only do minimal path
      // cleaning for display purposes.
      const sourceName = cleanKbLabel(toStringValue(d.source_name));
      const sourceType = toStringValue(d.source_type).toLowerCase();
      const explicitUrl = toStringValue(d.url);
      const snippetText = toStringValue(d.snippet);
      const snippetUrl = snippetText ? extractFirstUrl(snippetText) : undefined;
      const safeExplicitUrl = explicitUrl ? sanitizeUrl(explicitUrl) || undefined : undefined;
      const safeUrl = safeExplicitUrl || snippetUrl;
      if (!sourceName && !safeUrl) continue;

      // Use explicit source_type from backend if available
      const hasExplicitWebType = sourceType.includes('web');
      const hasUrl = typeof safeUrl === 'string';
      const isWeb = hasExplicitWebType || hasUrl || (sourceName ? isWebSource(sourceName) : false);

      if (import.meta.env.DEV) {
        console.log('[parseCitationSources] Detail:', { sourceName, source_type: sourceType, hasUrl, isWeb, url: safeUrl });
      }

      let url: string | undefined;
      let label = sourceName;

      if (isWeb) {
        if (safeUrl) {
          url = safeUrl;
          label = getDomainLabel(safeUrl);
        } else if (sourceName) {
          label = getDomainLabel(sourceName);
        }
      }

      if (!label || isRoutingToken(label)) continue;

      const dedupeKey = url ? `url:${url}` : `${isWeb ? 'web' : 'kb'}:${label.toLowerCase()}`;

      // Skip duplicates based on the final label (domain for web, sourceName for KB)
      if (seen.has(dedupeKey)) {
        if (import.meta.env.DEV) {
          console.log('[parseCitationSources] Skipping duplicate:', dedupeKey);
        }
        continue;
      }
      seen.add(dedupeKey);

      links.push({
        label,
        url,
        type: isWeb ? 'web' : 'knowledge_base',
      });
    }
  }

  if (links.length === 0 && Array.isArray(_citations.sources)) {
    debug('Falling back to citations.sources:', (_citations.sources as unknown[]).length, 'items', _citations.sources);
    for (const source of _citations.sources as unknown[]) {
      if (typeof source === 'string') {
        const sourceText = source.trim();
        if (!sourceText || isRoutingToken(sourceText)) continue;

        const isWeb = isWebSource(sourceText);
        if (import.meta.env.DEV) {
          console.log('[parseCitationSources] Processing source:', sourceText, 'isWeb:', isWeb);
        }
        const label = isWeb ? extractDomain(sourceText) : cleanKbLabel(sourceText);

        let url: string | undefined;
        if (isWeb) {
          const constructedUrl = sourceText.startsWith('http') ? sourceText : `https://${sourceText}`;
          url = sanitizeUrl(constructedUrl) || undefined;
        }

        const dedupeKey = url ? `url:${url}` : `${isWeb ? 'web' : 'kb'}:${label.toLowerCase()}`;
        if (seen.has(dedupeKey)) continue;
        seen.add(dedupeKey);

        links.push({
          label,
          url,
          type: isWeb ? 'web' : 'knowledge_base',
        });
        continue;
      }

      if (typeof source === 'object' && source !== null) {
        const src = source as Record<string, unknown>;
        const sourceName = cleanKbLabel(toStringValue(src.source_name ?? src.name ?? src.title ?? src.label));
        const sourceType = toStringValue(src.source_type ?? src.type).toLowerCase();
        const explicitUrl = toStringValue(src.url ?? src.link ?? src.href);
        const safeUrl = explicitUrl ? sanitizeUrl(explicitUrl) || undefined : undefined;

        if (!sourceName && !safeUrl) continue;

        const isWeb = sourceType.includes('web') || !!safeUrl || (sourceName ? isWebSource(sourceName) : false);
        let label = sourceName;
        if (isWeb) {
          if (safeUrl) {
            label = getDomainLabel(safeUrl);
          } else if (sourceName) {
            label = getDomainLabel(sourceName);
          }
        }

        if (!label || isRoutingToken(label)) continue;

        const dedupeKey = safeUrl ? `url:${safeUrl}` : `${isWeb ? 'web' : 'kb'}:${label.toLowerCase()}`;
        if (seen.has(dedupeKey)) continue;
        seen.add(dedupeKey);

        links.push({
          label,
          url: safeUrl,
          type: isWeb ? 'web' : 'knowledge_base',
        });
      }
    }
  }

  if (links.length === 0) {
    if (Array.isArray(citations)) {
      for (const item of citations) {
        if (typeof item === 'string' && item.trim()) {
          processCitationPart(item, links, seen, isWebSource, extractDomain);
        }
      }
    } else if (typeof citations === 'object' && citations !== null) {
      for (const [key, value] of Object.entries(citations)) {
        const lk = key.toLowerCase();
        if (lk === 'details' || lk === 'count' || lk === 'detail') continue;

        if (typeof value === 'string') {
          const parts = value.split(',').map(s => s.trim()).filter(Boolean);
          for (const part of parts) {
            processCitationPart(part, links, seen, isWebSource, extractDomain);
          }
        } else if (Array.isArray(value)) {
          for (const item of value) {
            if (typeof item === 'string' && item.trim()) {
              processCitationPart(item, links, seen, isWebSource, extractDomain);
            }
          }
        }
      }
    }
  }

  debug('Final links:', links.length, 'items', links.map(l => ({ label: l.label, type: l.type })));

  return links;
}

function processCitationPart(
  part: string,
  links: CitationSource[],
  seen: Set<string>,
  isWebSource: (str: string) => boolean,
  extractDomain: (str: string) => string
): void {
  const normalizedPart = part.trim();
  if (!normalizedPart || ROUTING_SOURCE_TOKENS.has(normalizedPart.toLowerCase())) {
    return;
  }

  if (normalizedPart.startsWith('http://') || normalizedPart.startsWith('https://') || normalizedPart.startsWith('(http')) {
    const cleanUrl = normalizedPart.replace(/^\(/, '').replace(/\)$/, '').trim();
    const safeUrl = sanitizeUrl(cleanUrl);
    try {
      if (!safeUrl) {
        if (!seen.has(normalizedPart)) {
          seen.add(normalizedPart);
          links.push({ label: normalizedPart, type: 'web' });
        }
        return;
      }

      const url = new URL(safeUrl);
      const domain = url.hostname.replace(/^www\./, '');
      const urlKey = `url:${safeUrl}`;

      if (!seen.has(urlKey)) {
        seen.add(urlKey);
        links.push({ label: domain, url: safeUrl, type: 'web' });
      }
    } catch {
      if (!seen.has(normalizedPart)) {
        seen.add(normalizedPart);
        links.push({ label: normalizedPart, type: 'web' });
      }
    }
  } else if (normalizedPart.includes('data\\') || normalizedPart.includes('data/')) {
    // Backend now automatically URL-decodes and strips file extensions,
    // but double/triple encoding or older payloads can still arrive with
    // %20 / + in the label.
    const cleaned = cleanKbLabel(normalizedPart);
    const key = `kb:${cleaned.toLowerCase()}`;
    if (cleaned && !seen.has(key)) {
      seen.add(key);
      links.push({ label: cleaned, type: 'knowledge_base' });
    }
  } else if (isWebSource(normalizedPart)) {
    const domain = extractDomain(normalizedPart);
    const webKey = `web:${domain}`;
    if (!seen.has(webKey)) {
      seen.add(webKey);
      const constructedUrl = normalizedPart.startsWith('http') ? normalizedPart : `https://${normalizedPart}`;
      const safeUrl = sanitizeUrl(constructedUrl);
      if (safeUrl) {
        links.push({ label: domain, url: safeUrl, type: 'web' });
      } else {
        links.push({ label: domain, type: 'web' });
      }
    }
  } else if (normalizedPart.length > 0 && normalizedPart !== '[object Object]') {
    // Backend now automatically URL-decodes source names, but double/triple
    // encoding or older payloads can still arrive with %20 / + in the label.
    const decoded = cleanKbLabel(normalizedPart);
    const key = `kb:${decoded.toLowerCase()}`;
    if (!seen.has(key)) {
      seen.add(key);
      links.push({ label: decoded, type: 'knowledge_base' });
    }
  }
}
