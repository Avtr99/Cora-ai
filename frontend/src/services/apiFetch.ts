import { useAuthStore } from '@/store/authStore';

/**
 * Fetch wrapper for API calls. A 401 means the instance access-key session is
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
