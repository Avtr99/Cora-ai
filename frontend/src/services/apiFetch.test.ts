import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { apiFetch, readErrorMessage } from './apiFetch';
import { useAuthStore } from '@/store/authStore';

describe('apiFetch', () => {
  beforeEach(() => {
    useAuthStore.setState({ status: 'open' });
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('marks auth required on a 401 and returns the response unchanged', async () => {
    const response = new Response('Unauthorized', { status: 401 });
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(response);

    const result = await apiFetch('/api/cora-health');

    expect(result).toBe(response);
    expect(useAuthStore.getState().status).toBe('required');
  });

  it.each([200, 500])('leaves the store unchanged on a %i response', async (status) => {
    const response = new Response('', { status });
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(response);

    const result = await apiFetch('/api/cora-health');

    expect(result).toBe(response);
    expect(useAuthStore.getState().status).toBe('open');
  });

  it('rejects when fetch rejects and does not change the store', async () => {
    vi.mocked(globalThis.fetch).mockRejectedValueOnce(new Error('network down'));

    await expect(apiFetch('/api/cora-health')).rejects.toThrow('network down');
    expect(useAuthStore.getState().status).toBe('open');
  });
});

describe('readErrorMessage', () => {
  it('returns field details from a validation error body', async () => {
    const response = new Response(
      JSON.stringify({
        error: 'validation_error',
        message: 'Request validation failed',
        details: {
          validation_errors: { username: "String should match pattern 'x'" },
        },
      }),
      { status: 422 }
    );

    await expect(readErrorMessage(response)).resolves.toBe(
      "username: String should match pattern 'x'"
    );
  });

  it('falls back to the message field and then to undefined', async () => {
    await expect(
      readErrorMessage(
        new Response(JSON.stringify({ message: 'Nope' }), { status: 400 })
      )
    ).resolves.toBe('Nope');
    await expect(
      readErrorMessage(new Response('oops', { status: 500 }))
    ).resolves.toBeUndefined();
  });
});
