import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { getSession, login, logout } from './authApi';
import { useAuthStore } from '@/store/authStore';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('authApi', () => {
  beforeEach(() => {
    useAuthStore.setState({ status: 'unknown' });
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  describe('getSession', () => {
    it('returns the parsed session status', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(
        jsonResponse({ required: true, authenticated: false })
      );

      const session = await getSession();

      expect(session).toEqual({ required: true, authenticated: false });
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
    it('resolves when the key is accepted and the cookie sticks', async () => {
      const mockFetch = vi.mocked(globalThis.fetch);
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
      mockFetch.mockResolvedValueOnce(jsonResponse({ required: true, authenticated: true }));

      await expect(login('secret-key')).resolves.toBeUndefined();

      expect(mockFetch).toHaveBeenNthCalledWith(1, '/api/auth/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: 'secret-key' }),
      });
    });

    it('throws "Invalid access key" on a 401 and does not mark the store', async () => {
      vi.mocked(globalThis.fetch).mockResolvedValueOnce(
        new Response('', { status: 401 })
      );

      await expect(login('wrong-key')).rejects.toThrow('Invalid access key');
      expect(useAuthStore.getState().status).toBe('unknown');
    });

    it('throws when the browser drops the session cookie', async () => {
      const mockFetch = vi.mocked(globalThis.fetch);
      mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));
      mockFetch.mockResolvedValueOnce(jsonResponse({ required: true, authenticated: false }));

      await expect(login('secret-key')).rejects.toThrow(
        'The browser did not keep the session cookie'
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
