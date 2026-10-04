import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AuthGate } from './AuthGate';
import { useAuthStore } from '@/store/authStore';
import { getSession, login } from '@/services/authApi';

vi.mock('@/services/authApi', () => ({
  getSession: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
}));

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  useAuthStore.setState({ status: 'unknown' });
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

async function submitLoginForm(key: string) {
  const input = container.querySelector<HTMLInputElement>('#instance-access-key')!;
  const form = container.querySelector('form')!;
  await act(async () => {
    setInputValue(input, key);
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
  });
}

describe('AuthGate', () => {
  it('renders the login page instead of children when a key is required', async () => {
    vi.mocked(getSession).mockResolvedValue({ required: true, authenticated: false });

    await renderGate();

    expect(container.querySelector('#instance-access-key')).not.toBeNull();
    expect(container.querySelector('[data-testid="app-content"]')).toBeNull();
  });

  it('renders children when auth is not required', async () => {
    vi.mocked(getSession).mockResolvedValue({ required: false, authenticated: true });

    await renderGate();

    expect(container.querySelector('[data-testid="app-content"]')).not.toBeNull();
    expect(container.querySelector('#instance-access-key')).toBeNull();
  });

  it('renders children when getSession rejects', async () => {
    vi.mocked(getSession).mockRejectedValue(new Error('backend down'));

    await renderGate();

    expect(container.querySelector('[data-testid="app-content"]')).not.toBeNull();
    expect(useAuthStore.getState().status).toBe('open');
  });

  it('shows the login page when the store flips to required after mount', async () => {
    vi.mocked(getSession).mockResolvedValue({ required: false, authenticated: true });
    await renderGate();
    expect(container.querySelector('[data-testid="app-content"]')).not.toBeNull();

    await act(async () => {
      useAuthStore.getState().markRequired();
    });

    expect(container.querySelector('#instance-access-key')).not.toBeNull();
    expect(container.querySelector('[data-testid="app-content"]')).toBeNull();
  });

  it('shows "Invalid access key" on a wrong key and authenticates on success', async () => {
    vi.mocked(getSession).mockResolvedValue({ required: true, authenticated: false });
    await renderGate();

    vi.mocked(login).mockRejectedValueOnce(new Error('Invalid access key'));
    await submitLoginForm('wrong-key');
    expect(container.querySelector('[role="alert"]')?.textContent).toBe('Invalid access key');
    expect(useAuthStore.getState().status).toBe('required');

    vi.mocked(login).mockResolvedValueOnce(undefined);
    await submitLoginForm('right-key');
    expect(useAuthStore.getState().status).toBe('authenticated');
  });
});
