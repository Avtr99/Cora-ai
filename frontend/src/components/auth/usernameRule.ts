/**
 * Shared client-side username rule. The backend stays the authority — it
 * trims and lowercases before matching the pattern, so this checks the same
 * normalized input and only fails fast before the request is sent.
 */

export const USERNAME_PATTERN = /^[a-z0-9][a-z0-9._-]{2,31}$/;

export const USERNAME_HINT =
  'lowercase letters, numbers, dots, hyphens or underscores (3–32 characters)';

export function usernameError(username: string): string | null {
  return USERNAME_PATTERN.test(username.trim().toLowerCase())
    ? null
    : `Usernames allow ${USERNAME_HINT}.`;
}
