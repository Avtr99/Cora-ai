/**
 * Parsing for the Berkeley "Certifications" column.
 *
 * The column is a semicolon-separated list. Two thirds of its non-empty values
 * are the single token "Emission Reduction" — Gold Standard's own product
 * label, present only on GOLD rows. It carries no quality or eligibility
 * information, so it is filtered out rather than rendered as a certification.
 */

import { classify, isNotCertification } from './certificationRules.mjs';
import type { CertificationKind } from './certificationRules.mjs';

export type { CertificationKind };

export interface Certification {
  label: string;
  kind: CertificationKind;
}

/** Split the raw column into meaningful certifications, preserving source order. */
export function parseCertifications(raw: string | undefined): Certification[] {
  if (!raw) return [];
  return raw
    .split(';')
    .map((t) => t.trim())
    .filter((t) => t && !isNotCertification(t))
    .map((label) => ({ label, kind: classify(label) }));
}
