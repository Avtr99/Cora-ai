import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import PasswordInput from './PasswordInput';

let container: HTMLDivElement;
let root: Root;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
});

async function renderInput() {
  await act(async () => {
    root.render(<PasswordInput value="" onChange={() => {}} />);
  });
}

describe('PasswordInput', () => {
  it('starts masked and reveals the value on toggle', async () => {
    await renderInput();

    const input = container.querySelector('input')!;
    const toggle = container.querySelector('button')!;
    expect(input.type).toBe('password');
    expect(toggle.getAttribute('aria-label')).toBe('Show password');

    await act(async () => {
      toggle.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(input.type).toBe('text');
    expect(toggle.getAttribute('aria-label')).toBe('Hide password');

    await act(async () => {
      toggle.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    });
    expect(input.type).toBe('password');
  });
});
