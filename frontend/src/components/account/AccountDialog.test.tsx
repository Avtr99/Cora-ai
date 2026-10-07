import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import AccountDialog from './AccountDialog';
import { useAuthStore } from '@/store/authStore';
import { changeOwnPassword } from '@/services/accountApi';

vi.mock('@/services/accountApi', () => ({
  changeOwnPassword: vi.fn(),
}));

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  useAuthStore.setState({
    status: 'authenticated',
    user: { id: 'owner', username: 'alice', role: 'owner' },
    ownerClaimRequired: false,
  });
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

async function renderDialog() {
  await act(async () => {
    root.render(<AccountDialog open onOpenChange={() => {}} />);
  });
}

function setInputValue(input: HTMLInputElement, value: string) {
  const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!;
  setter.call(input, value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

async function fillPasswords(current: string, next: string, confirm: string) {
  const inputs = Array.from(document.querySelectorAll<HTMLInputElement>('input[type="password"]'));
  await act(async () => {
    setInputValue(inputs[0], current);
    setInputValue(inputs[1], next);
    setInputValue(inputs[2], confirm);
  });
}

async function clickButton(text: string) {
  const button = Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find(
    (b) => b.textContent === text
  )!;
  await act(async () => {
    button.dispatchEvent(new MouseEvent('click', { bubbles: true }));
  });
}

describe('AccountDialog', () => {
  it('shows the signed-in user, role badge, and the password form', async () => {
    await renderDialog();

    expect(document.body.textContent).toContain('alice');
    expect(document.body.textContent).toContain('Owner');
    expect(document.querySelectorAll('input[type="password"]')).toHaveLength(3);
  });

  it('keeps the submit disabled until all fields are filled', async () => {
    await renderDialog();

    const submit = Array.from(document.querySelectorAll<HTMLButtonElement>('button')).find(
      (b) => b.textContent === 'Change password'
    )!;
    expect(submit.disabled).toBe(true);
    await fillPasswords('current-password', '', '');
    expect(submit.disabled).toBe(true);
  });

  it('blocks a too-short new password without calling the API', async () => {
    await renderDialog();
    await fillPasswords('current-password', 'short', 'short');
    await clickButton('Change password');

    expect(changeOwnPassword).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain('at least 15 characters');
  });

  it('calls changeOwnPassword and shows the saved banner', async () => {
    vi.mocked(changeOwnPassword).mockResolvedValue(undefined);
    await renderDialog();
    await fillPasswords('current-password', 'a-15-plus-char-password', 'a-15-plus-char-password');
    await clickButton('Change password');

    expect(changeOwnPassword).toHaveBeenCalledWith('current-password', 'a-15-plus-char-password');
    expect(document.body.textContent).toContain('Password changed');
  });
});
