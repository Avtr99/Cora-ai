import { useAuthStore } from '@/store/authStore';

/**
 * Fetch wrapper for API calls. A 401 means the session is
 * missing or expired, so it flips the app to the login screen via the auth
 * store. The response is returned unchanged; callers keep their own error
 * handling. Cookies flow via the default `credentials: 'same-origin'`.
 */
export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const response = await fetch(input, init);
  if (response.status === 401) {
    useAuthStore.getState().markRequired();
  }
  return response;
}

/**
 * Read the server's `message` field from an error response body.
 * Returns undefined for a non-JSON body or a missing/empty message, so the
 * caller picks its own fallback.
 */
export async function readErrorMessage(response: Response): Promise<string | undefined> {
  try {
    const body = (await response.json()) as {
      message?: unknown;
      details?: { validation_errors?: unknown };
    };
    const fieldErrors = body.details?.validation_errors;
    if (fieldErrors && typeof fieldErrors === 'object') {
      const parts = Object.entries(fieldErrors as Record<string, unknown>).map(
        ([field, detail]) => `${field}: ${String(detail)}`
      );
      if (parts.length > 0) return parts.join('; ');
    }
    return typeof body.message === 'string' && body.message.length > 0
      ? body.message
      : undefined;
  } catch {
    return undefined;
  }
}
