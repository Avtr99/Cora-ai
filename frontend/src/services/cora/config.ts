const parsedTimeout = Number.parseInt(import.meta.env.VITE_API_TIMEOUT_MS ?? '', 10);
const DEFAULT_API_TIMEOUT_MS = 60000;

export const IS_PROD = import.meta.env.PROD;

// Use the same relative proxy endpoints in both prod and local dev.
// - Production: reverse proxy (nginx/Caddy) rewrites /api/* to the backend.
// - Development: Vite dev server proxies /api/* to VITE_API_BASE.
export const API_ENDPOINT = '/api/cora-query';
export const API_STREAM_ENDPOINT = '/api/cora-query-stream';
export const HEALTH_ENDPOINT = '/api/cora-health';

export const API_TIMEOUT_MS = Number.isFinite(parsedTimeout) && parsedTimeout > 0
  ? parsedTimeout
  : DEFAULT_API_TIMEOUT_MS;

export const ENABLE_DEBUG_REASONS = (() => {
  const flagValue = import.meta.env.VITE_ENABLE_DEBUG_REASONS;
  if (typeof flagValue === 'string') {
    return flagValue.toLowerCase() === 'true';
  }
  // Default to true so reasoning is visible in all environments unless explicitly disabled
  return true;
})();

export const HEALTH_CHECK_TIMEOUT_MS = 5000;
