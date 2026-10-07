import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { changeOwnPassword, AccountApiError } from './accountApi';
import { useAuthStore } from '@/store/authStore';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('accountApi', () => {
  beforeEach(() => {
    useAuthStore.setState({
      status: 'authenticated',
      user: { id: 'owner', username: 'boss', role: 'owner' },
      ownerClaimRequired: false,
    });
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('changeOwnPassword PUTs both passwords', async () => {
    const mockFetch = vi.mocked(globalThis.fetch);
    mockFetch.mockResolvedValueOnce(new Response(null, { status: 204 }));

    await expect(
      changeOwnPassword('old-password-15+', 'new-password-15+')
    ).resolves.toBeUndefined();
    expect(mockFetch).toHaveBeenCalledWith('/api/account/password', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        current_password: 'old-password-15+',
        new_password: 'new-password-15+',
      }),
    });
  });

  it('changeOwnPassword: a 400 throws AccountApiError and keeps the session', async () => {
    // A wrong current password is a form error (400), not a dead session —
    // the user must stay signed in.
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      jsonResponse({ error: 'bad_request', message: 'Current password is wrong' }, 400)
    );

    const err = await changeOwnPassword('not-it', 'new-password-15+').catch(
      (e) => e
    );
    expect(err).toBeInstanceOf(AccountApiError);
    expect(err.status).toBe(400);
    expect(err.message).toBe('Current password is wrong');
    expect(useAuthStore.getState().status).toBe('authenticated');
  });
});
