import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ProviderToggle } from './ProviderToggle';
import { useAuthStore } from '@/store/authStore';
import { getAvailableProviders } from '@/services/llmSettingsApi';

vi.mock('@/services/llmSettingsApi', () => ({
  getAvailableProviders: vi.fn(),
  switchLLMProvider: vi.fn(),
  getCurrentProvider: vi.fn(),
}));

let container: HTMLDivElement;
let root: Root;
let queryClient: QueryClient;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  useAuthStore.setState({ status: 'open', user: null, ownerClaimRequired: false });
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  vi.mocked(getAvailableProviders).mockResolvedValue({
    current: 'gemini',
    available: [
      { slug: 'gemini', label: 'Google Gemini', provider: 'gemini', model: 'gemini-2.5-flash', has_api_key: true },
      { slug: 'ollama', label: 'Ollama', provider: 'ollama', model: 'llama3', has_api_key: true },
    ],
  });
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

async function renderToggle() {
  await act(async () => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <ProviderToggle />
      </QueryClientProvider>
    );
  });
  // react-query notifies subscribers on a scheduled microtask after the
  // queryFn promise resolves — flush so the result reaches the component.
  await act(async () => {});
}

// Poll by draining React's act queue on every iteration — `vi.waitFor`
// inside `act` polls timers but does not reliably flush queued renders when
// the worker is CPU-starved under a parallel suite run.
async function settleUntil(check: () => boolean, what: string) {
  for (let i = 0; i < 600; i++) {
    await act(async () => {});
    if (check()) return;
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
  throw new Error(`ProviderToggle test: ${what} never happened`);
}

/** Wait until the providers query resolved and React flushed the update. */
async function waitForQuerySettled() {
  await settleUntil(
    () =>
      vi.mocked(getAvailableProviders).mock.calls.length > 0 &&
      queryClient.getQueryState(['llm', 'providers'])?.status === 'success',
    'providers query never resolved'
  );
}

/** Wait until the toggle button is in the DOM. */
async function waitForButton() {
  await settleUntil(
    () => container.querySelector('button') !== null,
    'toggle button never rendered'
  );
}

// These tests poll the DOM while react-query notifies subscribers through
// React's act queue; under parallel-run CPU starvation that handoff can stall
// for seconds. Retry so a starved run re-executes cleanly instead of flaking.
describe('ProviderToggle', () => {
  it('renders for the owner with protection on', { retry: 2, timeout: 30_000 }, async () => {
    useAuthStore.setState({
      status: 'authenticated',
      user: { id: 'owner', username: 'boss', role: 'owner' },
      ownerClaimRequired: false,
    });
    await renderToggle();
    await waitForQuerySettled();
    await waitForButton();
  });

  it('renders with protection off', { retry: 2, timeout: 30_000 }, async () => {
    useAuthStore.setState({ status: 'open', user: null, ownerClaimRequired: false });
    await renderToggle();
    await waitForQuerySettled();
    await waitForButton();
  });

  it('renders nothing while signed out', async () => {
    useAuthStore.setState({
      status: 'required',
      user: null,
      ownerClaimRequired: false,
    });
    await renderToggle();
    await waitForQuerySettled();

    // The providers query ran and resolved — the owner check still hides it.
    expect(container.children.length).toBe(0);
  }, 30_000);
});
