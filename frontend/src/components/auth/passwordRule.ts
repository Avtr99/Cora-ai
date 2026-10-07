/**
 * Shared client-side password rule. The backend stays the authority — this
 * only fails fast before the request is sent.
 */

export const MIN_PASSWORD_LENGTH = 15;

export function passwordError(password: string): string | null {
  if ([...password].length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (new Set(password).size === 1) {
    return "Password must not be one repeated character.";
  }
  return null;
}
