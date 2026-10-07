/**
 * Session auth API.
 *
 * Uses plain `fetch` (not `apiFetch`) on purpose: the session endpoints are
 * excluded from auth on the backend, and a login 401 is "wrong credentials",
 * not an expired session — it must not call `markRequired`.
 */

import { readErrorMessage } from './apiFetch';

const SESSION_ENDPOINT = '/api/auth/session';
const OWNER_ENDPOINT = '/api/auth/owner';

export interface SessionUser {
  id: string;
  username: string;
  /** Single-owner model: the only account is the owner. */
  role: 'owner';
}

export interface SessionStatus {
  required: boolean;
  authenticated: boolean;
  owner_claim_required: boolean;
  user: SessionUser | null;
}

/** Read the server's `message` field from an error body, with a fallback. */
async function errorMessage(response: Response, fallback: string): Promise<string> {
  return (await readErrorMessage(response)) ?? fallback;
}

/**
 * A 204 means the cookie was set, but a dropped cookie (Secure cookie over
 * plain HTTP, blocked third-party cookies) means the session never sticks.
 * Verify before letting the UI flip to authenticated or it would loop back.
 */
async function verifySessionStuck(): Promise<SessionStatus> {
  const session = await getSession();
  if (!session.authenticated) {
    throw new Error(
      'The browser did not keep the session cookie. Use HTTPS, or set AUTH_COOKIE_SECURE=false for plain-HTTP testing.'
    );
  }
  return session;
}

export async function getSession(): Promise<SessionStatus> {
  const response = await fetch(SESSION_ENDPOINT);
  if (!response.ok) {
    throw new Error(`Failed to get session status: ${response.status}`);
  }
  return response.json();
}

/**
 * Sign in with a username and password. Resolves with the verified session
 * once the cookie sticks.
 */
export async function login(username: string, password: string): Promise<SessionStatus> {
  const response = await fetch(SESSION_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `Login failed with status ${response.status}`));
  }
  return verifySessionStuck();
}

/**
 * One-time owner setup: the instance access key claims the owner account and
 * signs in. Resolves with the verified session.
 */
export async function claimOwner(
  apiKey: string,
  username: string,
  password: string
): Promise<SessionStatus> {
  const response = await fetch(OWNER_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: apiKey, username, password }),
  });
  if (!response.ok) {
    throw new Error(await errorMessage(response, `Owner setup failed with status ${response.status}`));
  }
  return verifySessionStuck();
}

export async function logout(): Promise<void> {
  await fetch(SESSION_ENDPOINT, { method: 'DELETE' });
}
