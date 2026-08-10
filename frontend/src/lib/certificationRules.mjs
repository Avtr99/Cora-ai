/**
 * Shared certification classification rules.
 *
 * Kept in plain `.mjs` so the build-time CSV converter and the frontend
 * can both import the same source of truth without a transpile step.
 */

const NOT_A_CERTIFICATION = new Set(['emission reduction']);

/** True for raw registry product labels that are not third-party certifications. */
export function isNotCertification(label) {
  return NOT_A_CERTIFICATION.has(label.trim().toLowerCase());
}

/** Classify a single certification label into a standardized category. */
export function classify(label) {
  const l = label.toLowerCase();
  if (l.includes('icvcm') || l.includes('ccp')) return 'icvcm';
  if (l.includes('corsia')) return 'corsia';
  if (l.startsWith('ccb')) return 'ccb';
  return 'other';
}

/** Derive the most meaningful single certification from a raw semicolon-separated list. */
export function derivePrimaryCertification(raw) {
  if (!raw) return undefined;
  const labels = raw
    .split(';')
    .map((s) => s.trim())
    .filter((s) => s && !isNotCertification(s));
  if (labels.length === 0) return undefined;
  for (const label of labels) {
    const kind = classify(label);
    if (kind !== 'other') {
      return kind === 'icvcm' ? 'ICVCM' : kind === 'corsia' ? 'CORSIA' : 'CCB';
    }
  }
  return 'Other';
}
