import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { checkHealth } from './healthCheck';

vi.mock('./config', () => ({
  HEALTH_ENDPOINT: '/api/cora-health',
  HEALTH_CHECK_TIMEOUT_MS: 5000,
}));

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('checkHealth', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
    vi.restoreAllMocks();
  });

  it('reports reachable when the backend is unhealthy (H5 regression)', async () => {
    // A 200 with status "unhealthy" means the backend answered — it is
    // reachable. Component health is not the reachability gate.
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      jsonResponse({ status: 'unhealthy' })
    );

    const result = await checkHealth();

    expect(result.reachable).toBe(true);
    expect(result.status).toBe('unhealthy');
    expect(result.httpStatus).toBe(200);
  });

  it('reports reachable when the backend is degraded', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      jsonResponse({ status: 'degraded' })
    );

    const result = await checkHealth();

    expect(result.reachable).toBe(true);
    expect(result.status).toBe('degraded');
  });

  it('reports unreachable on a non-2xx response', async () => {
    vi.mocked(globalThis.fetch).mockResolvedValueOnce(
      jsonResponse({ detail: 'Service unavailable' }, 503)
    );

    const result = await checkHealth();

    expect(result.reachable).toBe(false);
    expect(result.httpStatus).toBe(503);
    expect(result.status).toContain('http 503');
  });

  it('reports unreachable when fetch rejects', async () => {
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.mocked(globalThis.fetch).mockRejectedValueOnce(
      new DOMException('aborted', 'AbortError')
    );

    const result = await checkHealth();

    expect(result.reachable).toBe(false);
    expect(result.status).toBe('error');
    expect(consoleSpy).toHaveBeenCalled();
  });
});
