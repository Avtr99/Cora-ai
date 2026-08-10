import type { VCMProject } from '@/types/project';

/**
 * Issuance activity of a project, derived from its issuance history.
 *
 * - `never`   — listed on a registry but has never issued a credit (~48% of
 *               the Berkeley database). Not stored: it is exactly
 *               `creditsIssued === 0`.
 * - `stalled` — issued at some point, but nothing recently.
 * - `issuing` — issued within the recent window.
 */
export type ProjectActivity = 'issuing' | 'stalled' | 'never';

/** A project is "stalled" once this many years have passed with no issuance. */
export const STALE_AFTER_YEARS = 3;

/**
 * Reference year for staleness.
 *
 * Derived from the dataset's own most recent issuance rather than the user's
 * clock, so an old data release does not gradually mark every project stalled.
 */
export function getReferenceYear(projects: VCMProject[]): number {
  let max = 0;
  for (const p of projects) {
    if (p.lastIssuanceYear && p.lastIssuanceYear > max) max = p.lastIssuanceYear;
  }
  return max || new Date().getFullYear();
}

export function getProjectActivity(p: VCMProject, referenceYear: number): ProjectActivity {
  if (!p.lastIssuanceYear) return 'never';
  return p.lastIssuanceYear < referenceYear - STALE_AFTER_YEARS ? 'stalled' : 'issuing';
}

export const ACTIVITY_LABELS: Record<ProjectActivity, string> = {
  issuing: 'Actively issuing',
  stalled: 'No recent issuance',
  never: 'Never issued',
};

export const ACTIVITY_DESCRIPTIONS: Record<ProjectActivity, string> = {
  issuing: `Issued credits within the last ${STALE_AFTER_YEARS} years.`,
  stalled: `Has issued credits before, but not in the last ${STALE_AFTER_YEARS} years.`,
  never: 'Listed on a registry but has never issued a credit.',
};
