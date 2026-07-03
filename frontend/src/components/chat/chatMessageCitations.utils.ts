import { CitationSource } from './CitationBadges';
import { sanitizeUrl } from '@/lib/security';
import type { CitationResponse } from '@/services/cora/types';

const INLINE_CITATION_REGEX = /\[(?:(Knowledge Base|Web)(?:,\s*cite:\s*([\d,\s]+))?|cite_(kb|web):\s*([\d,\s]+)|((?:source_\d+(?:,\s*)?)+))\]/g;
const ROUTING_SOURCE_TOKENS = new Set(['knowledge_base', 'web_search', 'hybrid', 'error_fallback']);

/** Decode URL-encoded source names defensively (e.g. vm0047%20arr%20v1.0). */
function decodeSourceLabel(label: string): string {
  if (!label || (!label.includes('%') && !label.includes('+'))) return label;
  try {
    let decoded = label.replace(/\+/g, ' ');
    let guard = 0;
    while (decoded.includes('%') && guard < 5) {
      const next = decodeURIComponent(decoded);
      if (next === decoded) break;
      decoded = next;
      guard++;
    }
    return decoded;
  } catch {
    return label;
  }
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

    return `[${match}](https://citation.internal/${type}/${cleanNums})`;
  });
}

export function parseCitationSources(citations: CitationResponse | Record<string, unknown> | unknown[]): CitationSource[] {
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
      // First, replace '+' with ' ' which is common in URL encoding
      let decodedStr = str.replace(/\+/g, ' ');

      // URL decode fully to handle %20, %2C, and potential double-encodings
      try {
        let preventInfiniteLoop = 0;
        while (decodedStr.includes('%') && preventInfiniteLoop < 5) {
          const decoded = decodeURIComponent(decodedStr);
          if (decoded === decodedStr) break;
          decodedStr = decoded;
          preventInfiniteLoop++;
        }
      } catch {
        // If decoding fails partway, continue with what we have
      }
      const cleanStr = decodedStr.replace(/^\(/, '').replace(/\)$/, '').trim();
      const url = cleanStr.startsWith('http') ? new URL(cleanStr) : new URL(`https://${cleanStr}`);
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

      // Backend now automatically URL-decodes and strips file extensions
      // We only do minimal path cleaning for display purposes
      const sourceName = decodeSourceLabel(toStringValue(d.source_name).replace(/^data[\\/]/, '').trim());
      const sourceType = toStringValue(d.source_type).toLowerCase();
      const explicitUrl = toStringValue(d.url);
      const snippetText = toStringValue(d.snippet);
      const snippetUrl = snippetText ? extractFirstUrl(snippetText) : undefined;
      const safeExplicitUrl = explicitUrl ? sanitizeUrl(explicitUrl) || undefined : undefined;
      const safeUrl = safeExplicitUrl || snippetUrl;
      if (!sourceName && !safeUrl) continue;

      // Use explicit source_type from backend if available (hybrid retrieval provides this)
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
        const label = isWeb ? extractDomain(sourceText) : decodeSourceLabel(sourceText);

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
        const sourceName = toStringValue(src.source_name ?? src.name ?? src.title ?? src.label)
          .replace(/^data[\\/]/, '')
          .trim();
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
    // Backend now automatically URL-decodes and strips file extensions
    const cleaned = normalizedPart.replace(/^data[\\/]/, '').trim();
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
    // Backend now automatically URL-decodes source names
    const key = `kb:${normalizedPart.toLowerCase()}`;
    if (!seen.has(key)) {
      seen.add(key);
      links.push({ label: normalizedPart, type: 'knowledge_base' });
    }
  }
}
