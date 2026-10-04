/**
 * Session auth API for the instance access key.
 *
 * Uses plain `fetch` (not `apiFetch`) on purpose: the session endpoints are
 * excluded from auth on the backend, and a login 401 is "wrong key", not an
 * expired session — it must not call `markRequired`.
 */

const SESSION_ENDPOINT = '/api/auth/session';

export interface SessionStatus {
  required: boolean;
  authenticated: boolean;
}

export async function getSession(): Promise<SessionStatus> {
  const response = await fetch(SESSION_ENDPOINT);
  if (!response.ok) {
    throw new Error(`Failed to get session status: ${response.status}`);
  }
  return response.json();
}

export async function login(key: string): Promise<void> {
  const response = await fetch(SESSION_ENDPOINT, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ api_key: key }),
  });
  if (response.status === 401) {
    throw new Error('Invalid access key');
  }
  if (!response.ok) {
    throw new Error(`Login failed with status ${response.status}`);
  }
  // The server returned 204 but a dropped cookie (Secure cookie over plain
  // HTTP, blocked third-party cookies) means the session never sticks. Verify
  // before letting the UI flip to authenticated or it would loop back here.
  const session = await getSession();
  if (!session.authenticated) {
    throw new Error(
      'The browser did not keep the session cookie. Use HTTPS, or set AUTH_COOKIE_SECURE=false for plain-HTTP testing.'
    );
  }
}

export async function logout(): Promise<void> {
  await fetch(SESSION_ENDPOINT, { method: 'DELETE' });
}
