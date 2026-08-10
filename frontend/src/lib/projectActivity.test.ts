import { describe, it, expect } from 'vitest';
import type { VCMProject } from '@/types/project';
import {
  getProjectActivity,
  getReferenceYear,
  STALE_AFTER_YEARS,
} from './projectActivity';

const project = (over: Partial<VCMProject> = {}): VCMProject => ({
  id: 'X1', name: 'X', registry: 'VCS', status: 'Registered', scope: 'S',
  type: 'T', reductionRemoval: 'Reduction', country: 'C', region: 'R',
  creditsIssued: 0, creditsRetired: 0, creditsRemaining: 0, ...over,
});

describe('getProjectActivity', () => {
  it('treats a project with no issuance history as never issued', () => {
    expect(getProjectActivity(project(), 2026)).toBe('never');
  });

  it('marks recent issuers as issuing', () => {
    expect(getProjectActivity(project({ lastIssuanceYear: 2026 }), 2026)).toBe('issuing');
    expect(getProjectActivity(project({ lastIssuanceYear: 2023 }), 2026)).toBe('issuing');
  });

  it('marks projects past the stale window as stalled', () => {
    expect(getProjectActivity(project({ lastIssuanceYear: 2022 }), 2026)).toBe('stalled');
    expect(getProjectActivity(project({ lastIssuanceYear: 2009 }), 2026)).toBe('stalled');
  });

  it('places the boundary exactly at STALE_AFTER_YEARS', () => {
    const ref = 2026;
    const edge = ref - STALE_AFTER_YEARS;
    expect(getProjectActivity(project({ lastIssuanceYear: edge }), ref)).toBe('issuing');
    expect(getProjectActivity(project({ lastIssuanceYear: edge - 1 }), ref)).toBe('stalled');
  });
});

describe('getReferenceYear', () => {
  it('uses the dataset max, not the wall clock, so old releases do not rot', () => {
    const projects = [
      project({ lastIssuanceYear: 2019 }),
      project({ lastIssuanceYear: 2026 }),
      project(),
    ];
    expect(getReferenceYear(projects)).toBe(2026);
  });

  it('falls back to the current year when nothing has ever issued', () => {
    expect(getReferenceYear([project()])).toBe(new Date().getFullYear());
  });
});
