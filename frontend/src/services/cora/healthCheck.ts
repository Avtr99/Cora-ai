import { HEALTH_CHECK_TIMEOUT_MS, HEALTH_ENDPOINT } from './config';

export async function checkHealth(): Promise<{ status: string; healthy: boolean; httpStatus?: number }> {
  const healthUrl = HEALTH_ENDPOINT;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), HEALTH_CHECK_TIMEOUT_MS);

  try {
    // Avoid stale cached responses from service workers or browser cache when
    // the backend has gone offline. A fresh health check is essential because
    // the chat UI prioritizes this signal over config/documents status.
    const response = await fetch(
      `${healthUrl}?_t=${Date.now()}`,
      { signal: controller.signal, cache: 'no-store' },
    );

    if (!response.ok) {
      return {
        status: `http ${response.status} ${response.statusText}`,
        healthy: false,
        httpStatus: response.status,
      };
    }

    const data = await response.json();
    return {
      status: data.status || 'unknown',
      healthy: data.status === 'healthy',
      httpStatus: response.status,
    };
  } catch (error) {
    console.error('Health check failed:', error);
    return { status: 'error', healthy: false };
  } finally {
    clearTimeout(timeoutId);
  }
}
