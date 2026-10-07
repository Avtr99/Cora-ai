import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { claimOwner, getSession, login, logout, type SessionStatus } from './authApi';
import { useAuthStore } from '@/store/authStore';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

const OWNER_USER = { id: 'owner', username: 'boss', role: 'owner' as const };

const openSession: SessionStatus = {
  required: false,
  authenticated: true,
  owner_claim_required: false,
  user: OWNER_USER,
};

describe('authApi', () => {
  beforeEach(() => {
    useAuthStore.setState({ status: 'unknown', user: null, ownerClaimRequired: false });
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('getSession', () => {
    it('returns the parsed session status including the user', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(jsonResponse(openSession));

      const session = await getSession();

      expect(session).toEqual(openSession);
      expect(vi.mocked(globalThis.fetch)).toHaveBeenCalledWith('/api/auth/session');
    });

    it('throws on a non-2xx response', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(
        new Response('', { status: 500 })
      );

      await expect(getSession()).rejects.toThrow('500');
    });
  });

  describe('login', () => {
    it('posts username and password, then resolves with the verified session', async () => {
      const mockFetch = vi.mocked(globalThis.fetch);
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
      mockFetch.mockResolvedValueOnce(jsonResponse({ ...openSession, required: true }));

      await expect(login('alice', 'a-15-plus-char-password')).resolves.toMatchObject({
        authenticated: true,
      });

      expect(mockFetch).toHaveBeenNthCalledWith(1, '/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: 'alice', password: 'a-15-plus-char-password' }),
      });
    });

    it('throws the server message on a 401 and does not mark the store', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(
        jsonResponse({ error: 'unauthorized', message: 'Invalid username or password' }, 401)
      );

      await expect(login('alice', 'wrong')).rejects.toThrow('Invalid username or password');
      expect(useAuthStore.getState().status).toBe('unknown');
    });

    it('maps a 429 to the server message', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(
        jsonResponse(
          { error: 'rate_limited', message: 'Too many sign-in attempts. Try again in a minute.' },
          429
        )
      );

      await expect(login('alice', 'wrong')).rejects.toThrow(
        'Too many sign-in attempts. Try again in a minute.'
      );
    });

    it('throws when the browser drops the session cookie', async () => {
      const mockFetch = vi.mocked(globalThis.fetch);
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
      mockFetch.mockResolvedValueOnce(
        jsonResponse({ required: true, authenticated: false, owner_claim_required: false, user: null })
      );

      await expect(login('alice', 'a-15-plus-char-password')).rejects.toThrow(
        'The browser did not keep the session cookie'
      );
    });
  });

  describe('claimOwner', () => {
    it('posts the access key, username, and password to /api/auth/owner', async () => {
      const mockFetch = vi.mocked(globalThis.fetch);
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
      mockFetch.mockResolvedValueOnce(jsonResponse({ ...openSession, required: true }));

      await expect(
        claimOwner('the-key', 'boss', 'a-15-plus-char-password')
      ).resolves.toMatchObject({ authenticated: true });

      expect(mockFetch).toHaveBeenNthCalledWith(1, '/api/auth/owner', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          api_key: 'the-key',
          username: 'boss',
          password: 'a-15-plus-char-password',
        }),
      });
    });

    it('throws the server message on a 401 (wrong key)', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(
        jsonResponse({ error: 'unauthorized', message: 'Invalid access key' }, 401)
      );

      await expect(claimOwner('bad', 'boss', 'a-15-plus-char-password')).rejects.toThrow(
        'Invalid access key'
      );
    });

    it('throws the server message on a 409 (already claimed)', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(
        jsonResponse({ error: 'conflict', message: 'Owner account already set up' }, 409)
      );

      await expect(claimOwner('the-key', 'boss', 'a-15-plus-char-password')).rejects.toThrow(
        'Owner account already set up'
      );
    });
  });

  describe('logout', () => {
    it('sends a DELETE to the session endpoint', async () => {
      const mockFetch = vi.mocked(globalThis.fetch);
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

      await logout();

      expect(mockFetch).toHaveBeenCalledWith('/api/auth/session', { method: 'DELETE' });
    });
  });
});
