import { describe, expect, it } from 'vitest';
import { usernameError } from './usernameRule';

describe('usernameError', () => {
  it('accepts valid usernames, including ones the backend normalizes', () => {
    expect(usernameError('alice')).toBeNull();
    expect(usernameError('jane.doe')).toBeNull();
    expect(usernameError('user-name_1')).toBeNull();
    expect(usernameError('  Alice ')).toBeNull();
  });

  it('rejects emails and other disallowed shapes', () => {
    expect(usernameError('alice@example.org')).not.toBeNull();
    expect(usernameError('a b')).not.toBeNull();
    expect(usernameError('-alice')).not.toBeNull();
    expect(usernameError('ab')).not.toBeNull();
    expect(usernameError('a'.repeat(33))).not.toBeNull();
  });
});
