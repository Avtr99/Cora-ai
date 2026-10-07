/**
 * Self-service account API — the owner's own password change lives under
 * `/api/account/password`.
 *
 * Dev proxy: `/api/account` is rewritten to `/v1/account`
 * (vite.config.ts). In production the same prefix is served by the
 * FastAPI `/api` mount.
 */

import { apiFetch, readErrorMessage } from './apiFetch';

const ACCOUNT_ENDPOINT = '/api/account';

export class AccountApiError extends Error {
  constructor(
    public readonly status: number,
    message?: string
  ) {
    super(message ?? `Account request failed with status ${status}`);
    this.name = 'AccountApiError';
  }
}

/**
 * Change the caller's own password. Every other session ends; this one
 * survives. 400 on a wrong current password, 429 after five tries.
 */
export async function changeOwnPassword(
  currentPassword: string,
  newPassword: string
): Promise<void> {
  const response = await apiFetch(`${ACCOUNT_ENDPOINT}/password`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
  if (!response.ok) {
    throw new AccountApiError(response.status, await readErrorMessage(response));
  }
}
