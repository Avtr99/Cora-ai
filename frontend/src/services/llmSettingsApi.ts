/**
 * LLM Settings API service.
 *
 * Provides functions for getting/setting the LLM provider configuration
 * and listing available models from a provider (e.g. Ollama).
 */

const SETTINGS_BASE = '/api/v1/settings';

export interface LLMSettings {
  is_configured: boolean;
  provider: string | null;
  has_api_key: boolean;
  base_url: string | null;
  model_main: string | null;
  model_lite: string | null;
  organization: string | null;
}

export interface LLMModel {
  name: string;
  size_bytes: number | null;
  parameter_size: string | null;
  family: string | null;
}

export interface LLMModelsResponse {
  models: LLMModel[];
}

export interface LLMSettingsUpdate {
  provider: string;
  api_key?: string | null;
  base_url?: string | null;
  model_main?: string | null;
  model_lite?: string | null;
  organization?: string | null;
}

/**
 * Get current LLM settings. The API key is never returned.
 */
export async function getLLMSettings(): Promise<LLMSettings> {
  const response = await fetch(`${SETTINGS_BASE}/llm`);
  if (!response.ok) {
    throw new Error(`Failed to get LLM settings: ${response.status}`);
  }
  return response.json();
}

/**
 * Update LLM provider configuration.
 * If api_key is null/undefined, the existing key is preserved.
 */
export async function updateLLMSettings(update: LLMSettingsUpdate): Promise<LLMSettings> {
  const response = await fetch(`${SETTINGS_BASE}/llm`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to update LLM settings: ${error}`);
  }
  return response.json();
}

/**
 * List available models from a provider (e.g. Ollama /api/tags).
 * For providers that don't support model listing, returns empty list.
 */
export async function listLLMModels(baseUrl: string): Promise<LLMModel[]> {
  const params = new URLSearchParams({ base_url: baseUrl });
  const response = await fetch(`${SETTINGS_BASE}/llm/models?${params}`);
  if (!response.ok) {
    const error = await response.text();
    throw new Error(`Failed to list models: ${error}`);
  }
  const data: LLMModelsResponse = await response.json();
  return data.models;
}

/**
 * Check if the LLM is configured. Convenience wrapper.
 */
export async function isLLMConfigured(): Promise<boolean> {
  try {
    const settings = await getLLMSettings();
    return settings.is_configured;
  } catch {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Full configuration status
// ---------------------------------------------------------------------------

export interface ProviderStatus {
  provider: string;
  has_api_key: boolean;
  model: string | null;
  is_configured: boolean;
  warning: string | null;
}

export interface QdrantInfo {
  collection?: string;
  vector_dim?: number;
  points_count?: number;
  error?: string;
}

export interface ConfigStatus {
  ready: boolean;
  llm: ProviderStatus;
  embeddings: ProviderStatus;
  reranker: ProviderStatus;
  search: ProviderStatus;
  qdrant: QdrantInfo | null;
  warnings: string[];
  /** True when the backend can answer grounded questions (LLM configured + KB or web search ready). */
  chat_ready: boolean;
  /** True when the Qdrant knowledge base has indexed documents. */
  kb_ready: boolean;
  /** True when a web search provider other than 'none' is configured. */
  search_ready: boolean;
}

/**
 * Get full configuration status with validation warnings.
 * Checks all providers and Qdrant dimension compatibility.
 */
export async function getConfigStatus(): Promise<ConfigStatus> {
  const response = await fetch(`${SETTINGS_BASE}/status`);
  if (!response.ok) {
    throw new Error(`Failed to get config status: ${response.status}`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// LLM connection test
// ---------------------------------------------------------------------------

export interface LLMTestRequest {
  provider: string;
  api_key?: string | null;
  base_url?: string | null;
  model_main?: string | null;
}

export interface LLMTestResult {
  success: boolean;
  message: string;
  detail?: string | null;
}

/**
 * Test an LLM configuration before saving it.
 *
 * Makes a lightweight API call to the provider to verify the API key,
 * model name, and base URL are all valid. Does NOT save the settings.
 *
 * Throws a network error if the backend is unreachable.
 * Returns { success: false, ... } if the test fails (e.g. bad key).
 */
export async function testLLMConnection(req: LLMTestRequest): Promise<LLMTestResult> {
  const response = await fetch(`${SETTINGS_BASE}/llm/test`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Test request failed: ${response.status} ${text}`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Embedding provider settings
// ---------------------------------------------------------------------------

export interface EmbeddingSettings {
  provider: string;
  model: string;
  dim: number;
  has_api_key: boolean;
  ollama_base_url: string | null;
  is_configured: boolean;
}

export interface EmbeddingSettingsUpdate {
  provider: string;
  model?: string | null;
  dim?: number | null;
  api_key?: string | null;
  ollama_base_url?: string | null;
}

export async function getEmbeddingSettings(): Promise<EmbeddingSettings> {
  const response = await fetch(`${SETTINGS_BASE}/embeddings`);
  if (!response.ok) {
    throw new Error(`Failed to get embedding settings: ${response.status}`);
  }
  return response.json();
}

export async function updateEmbeddingSettings(update: EmbeddingSettingsUpdate): Promise<EmbeddingSettings> {
  const response = await fetch(`${SETTINGS_BASE}/embeddings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to update embedding settings: ${response.status} ${text}`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Web search provider settings
// ---------------------------------------------------------------------------

export interface SearchSettings {
  provider: string;
  has_api_key: boolean;
  is_configured: boolean;
}

export interface SearchSettingsUpdate {
  provider: string;
  api_key?: string | null;
}

export async function getSearchSettings(): Promise<SearchSettings> {
  const response = await fetch(`${SETTINGS_BASE}/search`);
  if (!response.ok) {
    throw new Error(`Failed to get search settings: ${response.status}`);
  }
  return response.json();
}

export async function updateSearchSettings(update: SearchSettingsUpdate): Promise<SearchSettings> {
  const response = await fetch(`${SETTINGS_BASE}/search`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to update search settings: ${response.status} ${text}`);
  }
  return response.json();
}

// ---------------------------------------------------------------------------
// Reranker provider settings
// ---------------------------------------------------------------------------

export interface RerankerSettings {
  provider: string;
  model: string | null;
  has_api_key: boolean;
  is_configured: boolean;
}

export interface RerankerSettingsUpdate {
  provider: string;
  model?: string | null;
  api_key?: string | null;
}

export async function getRerankerSettings(): Promise<RerankerSettings> {
  const response = await fetch(`${SETTINGS_BASE}/reranker`);
  if (!response.ok) {
    throw new Error(`Failed to get reranker settings: ${response.status}`);
  }
  return response.json();
}

export async function updateRerankerSettings(update: RerankerSettingsUpdate): Promise<RerankerSettings> {
  const response = await fetch(`${SETTINGS_BASE}/reranker`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Failed to update reranker settings: ${response.status} ${text}`);
  }
  return response.json();
}
