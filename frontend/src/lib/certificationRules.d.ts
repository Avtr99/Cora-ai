export type CertificationKind = 'icvcm' | 'corsia' | 'ccb' | 'other';

export function isNotCertification(label: string): boolean;

export function classify(label: string): CertificationKind;

export function derivePrimaryCertification(raw: string | undefined): string | undefined;
