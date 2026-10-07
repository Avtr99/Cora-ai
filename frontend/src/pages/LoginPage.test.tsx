import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import LoginPage from './LoginPage';
import { useAuthStore } from '@/store/authStore';
import { login, claimOwner, type SessionStatus } from '@/services/authApi';

vi.mock('@/services/authApi', () => ({
  login: vi.fn(),
  claimOwner: vi.fn(),
  getSession: vi.fn(),
  logout: vi.fn(),
}));

const claimedSession: SessionStatus = {
  required: true,
  authenticated: true,
  owner_claim_required: false,
  user: { id: 'owner', username: 'boss', role: 'owner' },
};

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  useAuthStore.setState({ status: 'required', user: null, ownerClaimRequired: false });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

async function renderPage() {
  await act(async () => {
    root.render(<LoginPage />);
  });
}

function setInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

async function fill(fields: Record<string, string>) {
  await act(async () => {
    for (const [id, value] of Object.entries(fields)) {
      setInputValue(container.querySelector<HTMLInputElement>(`#${id}`)!, value);
    }
  });
}

async function submit() {
  const form = container.querySelector('form')!;
  await act(async () => {
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
}

describe('LoginPage', () => {
  it('shows the sign-in form when the owner is already claimed', async () => {
    await renderPage();

    expect(container.querySelector('#login-username')).not.toBeNull();
    expect(container.querySelector('#login-password')).not.toBeNull();
    expect(container.querySelector('#claim-access-key')).toBeNull();
  });

  it('shows the claim form first when ownerClaimRequired', async () => {
    useAuthStore.setState({ ownerClaimRequired: true });
    await renderPage();

    expect(container.querySelector('#claim-access-key')).not.toBeNull();
    expect(container.querySelector('#claim-password-confirm')).not.toBeNull();
    expect(container.querySelector('#login-username')).toBeNull();
  });

  it('the claim form links back to the sign-in form', async () => {
    useAuthStore.setState({ ownerClaimRequired: true });
    await renderPage();

    const link = Array.from(container.querySelectorAll('button')).find(
      (b) => b.textContent === 'Already have an account? Sign in'
    )!;
    await act(async () => {
      link.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });

    expect(container.querySelector('#login-username')).not.toBeNull();
    expect(container.querySelector('#claim-access-key')).toBeNull();
  });

  it('calls login with the username and password', async () => {
    vi.mocked(login).mockResolvedValue(claimedSession);
    await renderPage();

    await fill({ 'login-username': 'alice', 'login-password': 'a-15-plus-char-password' });
    await submit();

    expect(login).toHaveBeenCalledWith('alice', 'a-15-plus-char-password');
    expect(useAuthStore.getState().status).toBe('authenticated');
  });

  it('blocks claim submit when the passwords do not match', async () => {
    useAuthStore.setState({ ownerClaimRequired: true });
    await renderPage();

    await fill({
      'claim-access-key': 'the-key',
      'claim-username': 'boss',
      'claim-password': 'a-15-plus-char-password',
      'claim-password-confirm': 'a-different-password!',
    });
    await submit();

    expect(claimOwner).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]')?.textContent).toBe(
      'Passwords do not match.'
    );
  });

  it('blocks claim submit when the password is under 15 characters', async () => {
    useAuthStore.setState({ ownerClaimRequired: true });
    await renderPage();

    await fill({
      'claim-access-key': 'the-key',
      'claim-username': 'boss',
      'claim-password': 'short',
      'claim-password-confirm': 'short',
    });
    await submit();

    expect(claimOwner).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      'at least 15 characters'
    );
  });

  it('blocks sign-in when the username is not a valid format', async () => {
    await renderPage();

    await fill({ 'login-username': 'alice@example.org', 'login-password': 'a-15-plus-char-password' });
    await submit();

    expect(login).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      'Usernames allow'
    );
  });

  it('blocks claim when the username is not a valid format', async () => {
    useAuthStore.setState({ ownerClaimRequired: true });
    await renderPage();

    await fill({
      'claim-access-key': 'the-key',
      'claim-username': 'alice@example.org',
      'claim-password': 'a-15-plus-char-password',
      'claim-password-confirm': 'a-15-plus-char-password',
    });
    await submit();

    expect(claimOwner).not.toHaveBeenCalled();
    expect(container.querySelector('[role="alert"]')?.textContent).toContain(
      'Usernames allow'
    );
  });

  it('calls claimOwner and applies the returned session', async () => {
    useAuthStore.setState({ ownerClaimRequired: true });
    vi.mocked(claimOwner).mockResolvedValue(claimedSession);
    await renderPage();

    await fill({
      'claim-access-key': 'the-key',
      'claim-username': 'boss',
      'claim-password': 'a-15-plus-char-password',
      'claim-password-confirm': 'a-15-plus-char-password',
    });
    await submit();

    expect(claimOwner).toHaveBeenCalledWith('the-key', 'boss', 'a-15-plus-char-password');
    expect(useAuthStore.getState().status).toBe('authenticated');
    expect(useAuthStore.getState().user?.username).toBe('boss');
  });
});
