import { describe, it, expect } from 'vitest';
import { parseCertifications } from './certifications';

describe('parseCertifications', () => {
  it('returns nothing for empty input', () => {
    expect(parseCertifications(undefined)).toEqual([]);
    expect(parseCertifications('')).toEqual([]);
  });

  it('drops the Gold Standard "Emission Reduction" product label', () => {
    // 1,964 of 2,904 non-empty values in v2026-06 are exactly this.
    expect(parseCertifications('Emission Reduction')).toEqual([]);
  });

  it('splits and classifies real certifications', () => {
    expect(parseCertifications('ICVCM CCP; CORSIA 2021-2023 (Pilot Phase)')).toEqual([
      { label: 'ICVCM CCP', kind: 'icvcm' },
      { label: 'CORSIA 2021-2023 (Pilot Phase)', kind: 'corsia' },
    ]);
  });

  it('classifies CCB variants', () => {
    expect(parseCertifications('CCB-Biodiversity Gold')).toEqual([
      { label: 'CCB-Biodiversity Gold', kind: 'ccb' },
    ]);
  });

  it('keeps real certifications when mixed with the noise token', () => {
    expect(parseCertifications('Emission Reduction; ICVCM CCP')).toEqual([
      { label: 'ICVCM CCP', kind: 'icvcm' },
    ]);
  });

  it('ignores empty segments and stray whitespace', () => {
    expect(parseCertifications(' Social Carbon ;; ')).toEqual([
      { label: 'Social Carbon', kind: 'other' },
    ]);
  });
});
