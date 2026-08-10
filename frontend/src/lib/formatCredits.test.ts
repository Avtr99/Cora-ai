import { describe, it, expect } from 'vitest';
import { formatCredits } from './formatCredits';

describe('formatCredits', () => {
  it('scales positive values', () => {
    expect(formatCredits(1_500_000_000)).toBe('1.5B');
    expect(formatCredits(1_500_000)).toBe('1.5M');
    expect(formatCredits(1_500)).toBe('2K');
    expect(formatCredits(500)).toBe('500');
    expect(formatCredits(0)).toBe('0');
  });

  it('scales negative values by magnitude', () => {
    // Real over-retired projects in the Berkeley v2026-06 dataset.
    expect(formatCredits(-151_516)).toBe('-152K'); // ACR0212
    expect(formatCredits(-180_544)).toBe('-181K'); // ACR0420
    expect(formatCredits(-595)).toBe('-595'); // GS440
    expect(formatCredits(-2_500_000)).toBe('-2.5M');
  });

  it('does not fall through to raw locale output for large negatives', () => {
    expect(formatCredits(-151_516)).not.toContain(',');
  });
});
