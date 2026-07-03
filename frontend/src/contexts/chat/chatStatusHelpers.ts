/**
 * Pure helpers for parsing and formatting SSE status messages
 * from the Cora streaming API into user-friendly text.
 *
 * Status values are defined in FRONTEND_INTEGRATION.md (§ Status Values):
 * accepted, processing, routing, retrieving, generating,
 * searching_web, searching_hybrid.
 *
 * The backend may also send a free-form `message` field or a human-readable
 * stage string (e.g. "Retrieving (45%)"), so we match by substring against
 * the lowercased source. Ordering is intentional: more specific patterns
 * (e.g. searching_web) precede generic ones (e.g. web) so a stage like
 * "searching_web" does not collapse into the generic web label.
 */

export function parseStageAndProgress(raw?: string): { stage: string; progress?: number } {
  if (!raw) return { stage: '' };
  const m = raw.match(/^(.+?)\s*\((\d+(?:\.\d+)?)%\)\s*$/);
  if (m) {
    return { stage: m[1].trim(), progress: parseFloat(m[2]) };
  }
  return { stage: raw.trim() };
}

export function friendlyStatusText(rawMessage?: string, rawStatus?: string): string {
  // Try the message first, then fall back to the raw status field
  const source = rawMessage && rawMessage.trim().length > 0 ? rawMessage : rawStatus;
  if (!source) return 'Working on your query';

  const { stage, progress: _progress } = parseStageAndProgress(source);
  const s = stage.toLowerCase();

  if (s.includes('accept')) {
    return 'Query accepted';
  }
  if (s.includes('processing')) {
    return 'Processing your query';
  }
  if (s.includes('rewrite') || s.includes('clarif')) {
    return 'Refining your query';
  }
  if (s.includes('route') || s.includes('intent') || s.includes('analyz')) {
    return 'Finding relevant data';
  }
  if (s.includes('retriev') || s.includes('kb') || s.includes('knowledge')) {
    return 'Searching knowledge base';
  }
  if (s.includes('searching_web') || s.includes('searching web')) {
    return 'Searching the web';
  }
  if (s.includes('searching_hybrid') || s.includes('searching hybrid') || s.includes('hybrid')) {
    return 'Searching knowledge base and web';
  }
  if (s.includes('web') || s.includes('internet') || s.includes('external')) {
    return 'Searching the web';
  }
  if (s.includes('generat')) {
    return 'Generating answer';
  }
  if (s.includes('summar')) {
    return 'Synthesizing answer';
  }
  if (s.includes('valid') || s.includes('check') || s.includes('quality')) {
    return 'Verifying answer';
  }
  if (s.includes('answer') || s.includes('draft')) {
    return 'Generating answer';
  }
  return 'Working on your query';
}
