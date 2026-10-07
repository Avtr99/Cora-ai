import { describe, expect, it } from 'vitest';
import { MIN_PASSWORD_LENGTH, passwordError } from './passwordRule';

describe('passwordError', () => {
  it('rejects passwords under the minimum length and accepts the boundary', () => {
    expect(passwordError('short')).toBe(
      `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
    );
    expect(passwordError('a'.repeat(MIN_PASSWORD_LENGTH - 1))).toBe(
      `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`
    );
    expect(passwordError('xy'.repeat(MIN_PASSWORD_LENGTH))).toBeNull();
  });

  it('rejects one repeated character', () => {
    expect(passwordError('a'.repeat(MIN_PASSWORD_LENGTH))).toBe(
      'Password must not be one repeated character.'
    );
    expect(passwordError('9'.repeat(30))).toBe(
      'Password must not be one repeated character.'
    );
    expect(passwordError('ab'.repeat(MIN_PASSWORD_LENGTH))).toBeNull();
  });
});
