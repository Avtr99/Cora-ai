import React, { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import SettingsDialog from './SettingsDialog';
import { useAuthStore } from '@/store/authStore';
import { useSettingsDialogStore } from '@/store/settingsDialogStore';
import {
  getLLMSettings,
  getEmbeddingSettings,
  getSearchSettings,
  getConfigStatus,
} from '@/services/llmSettingsApi';

vi.mock('@/services/llmSettingsApi', () => ({
  getLLMSettings: vi.fn(),
  getEmbeddingSettings: vi.fn(),
  getSearchSettings: vi.fn(),
  getConfigStatus: vi.fn(),
  testLLMConnection: vi.fn(),
  updateLLMSettings: vi.fn(),
  updateEmbeddingSettings: vi.fn(),
  updateSearchSettings: vi.fn(),
  listLLMModels: vi.fn(),
  getAvailableProviders: vi.fn(),
  switchLLMProvider: vi.fn(),
}));

let container: HTMLDivElement;
let root: Root;
let queryClient: QueryClient;

beforeEach(() => {
  vi.stubGlobal('IS_REACT_ACT_ENVIRONMENT', true);
  useAuthStore.setState({ status: 'open', user: null, ownerClaimRequired: false });
  useSettingsDialogStore.setState({ open: true, tab: 'llm' });
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);

  vi.mocked(getLLMSettings).mockResolvedValue({
    is_configured: true,
    provider: 'gemini',
    has_api_key: true,
    base_url: null,
    model_main: 'gemini-2.5-flash',
    model_lite: null,
    organization: null,
  });
  vi.mocked(getEmbeddingSettings).mockResolvedValue({
    provider: 'voyage',
    model: 'voyage-4-lite',
    dim: 1024,
    has_api_key: true,
    ollama_base_url: null,
    is_configured: true,
  });
  vi.mocked(getSearchSettings).mockResolvedValue({
    provider: 'tavily',
    has_api_key: true,
    is_configured: true,
  });
  vi.mocked(getConfigStatus).mockResolvedValue(null as never);
});

afterEach(async () => {
  await act(async () => root.unmount());
  container.remove();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

async function renderDialog() {
  await act(async () => {
    root.render(
      <QueryClientProvider client={queryClient}>
        <SettingsDialog open onOpenChange={() => {}} />
      </QueryClientProvider>
    );
  });
  // The settings load resolves via promises + state; flush it.
  await act(async () => {});
}

function tabList(): string[] {
  return Array.from(document.querySelectorAll('[role="tab"]')).map(
    (t) => t.textContent ?? ''
  );
}

function buttonTexts(): string[] {
  return Array.from(document.querySelectorAll('button')).map(
    (b) => b.textContent ?? ''
  );
}

describe('SettingsDialog', () => {
  it('shows the three provider tabs with save and test controls', async () => {
    await renderDialog();

    expect(tabList()).toEqual(['AI Model', 'Embeddings', 'Web Search']);

    const buttons = buttonTexts();
    expect(buttons).toContain('Save');
    expect(buttons).toContain('Test connection');
  });

  it('shows the same editable settings when signed in as the owner', async () => {
    useAuthStore.setState({
      status: 'authenticated',
      user: { id: 'owner', username: 'boss', role: 'owner' },
      ownerClaimRequired: false,
    });
    await renderDialog();

    expect(tabList()).toEqual(['AI Model', 'Embeddings', 'Web Search']);
    expect(buttonTexts()).toContain('Save');
  });
});
