import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthGate } from './AuthGate';
import { useAuthStore } from '@/store/authStore';
import { getSession, login, type SessionStatus } from '@/services/authApi';

vi.mock('@/services/authApi', () => ({
  getSession: vi.fn(),
  login: vi.fn(),
  claimOwner: vi.fn(),
  logout: vi.fn(),
}));

const unclaimedSession: SessionStatus = {
  required: true,
  authenticated: false,
  owner_claim_required: true,
  user: null,
};

const ownerSession: SessionStatus = {
  required: true,
  authenticated: true,
  owner_claim_required: false,
  user: { id: 'u1', username: 'alice', role: 'owner' },
};

const openSession: SessionStatus = {
  required: false,
  authenticated: true,
  owner_claim_required: false,
  user: { id: 'owner', username: 'boss', role: 'owner' },
};

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  useAuthStore.setState({ status: 'unknown', user: null, ownerClaimRequired: false });
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

async function renderGate() {
  await act(async () => {
    root.render(
      <MemoryRouter>
        <AuthGate>
          <div data-testid="app-content">app</div>
        </AuthGate>
      </MemoryRouter>
    );
  });
}

function setInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

async function submitLoginForm(username: string, password: string) {
  const userInput = container.querySelector<HTMLInputElement>('#login-username')!;
  const passwordInput = container.querySelector<HTMLInputElement>('#login-password')!;
  const form = container.querySelector('form')!;
  await act(async () => {
    setInputValue(userInput, username);
    setInputValue(passwordInput, password);
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
}

describe('AuthGate', () => {
  it('renders the login page instead of children when a sign-in is required', async () => {
    vi.mocked(getSession).mockResolvedValue({
      required: true,
      authenticated: false,
      owner_claim_required: false,
      user: null,
    });

    await renderGate();

    expect(container.querySelector('#login-username')).not.toBeNull();
    expect(container.querySelector('[data-testid="app-content"]')).toBeNull();
  });

  it('renders children when auth is not required', async () => {
    vi.mocked(getSession).mockResolvedValue(openSession);

    await renderGate();

    expect(container.querySelector('[data-testid="app-content"]')).not.toBeNull();
    expect(container.querySelector('#login-username')).toBeNull();
  });

  it('stores the user and ownerClaimRequired from getSession', async () => {
    vi.mocked(getSession).mockResolvedValue(ownerSession);

    await renderGate();

    expect(useAuthStore.getState().status).toBe('authenticated');
    expect(useAuthStore.getState().user).toEqual(ownerSession.user);
    expect(useAuthStore.getState().ownerClaimRequired).toBe(false);
  });

  it('stores ownerClaimRequired for an unclaimed instance', async () => {
    vi.mocked(getSession).mockResolvedValue(unclaimedSession);

    await renderGate();

    expect(useAuthStore.getState().ownerClaimRequired).toBe(true);
    expect(useAuthStore.getState().status).toBe('required');
  });

  it('renders children when getSession rejects', async () => {
    vi.mocked(getSession).mockRejectedValue(new Error('backend down'));

    await renderGate();

    expect(container.querySelector('[data-testid="app-content"]')).not.toBeNull();
    expect(useAuthStore.getState().status).toBe('open');
  });

  it('shows the login page when the store flips to required after mount', async () => {
    vi.mocked(getSession).mockResolvedValue(openSession);
    await renderGate();
    expect(container.querySelector('[data-testid="app-content"]')).not.toBeNull();

    await act(async () => {
      useAuthStore.getState().markRequired();
    });

    expect(container.querySelector('#login-username')).not.toBeNull();
    expect(container.querySelector('[data-testid="app-content"]')).toBeNull();
  });

  it('shows the server error on a wrong password and authenticates on success', async () => {
    vi.mocked(getSession).mockResolvedValue({
      required: true,
      authenticated: false,
      owner_claim_required: false,
      user: null,
    });
    await renderGate();

    vi.mocked(login).mockRejectedValueOnce(new Error('Invalid username or password'));
    await submitLoginForm('alice', 'wrong-password');
    expect(container.querySelector('[role="alert"]')?.textContent).toBe(
      'Invalid username or password'
    );
    expect(useAuthStore.getState().status).toBe('required');

    vi.mocked(login).mockResolvedValueOnce(ownerSession);
    await submitLoginForm('alice', 'a-15-plus-char-password');
    expect(useAuthStore.getState().status).toBe('authenticated');
    expect(useAuthStore.getState().user?.username).toBe('alice');
  });
});
