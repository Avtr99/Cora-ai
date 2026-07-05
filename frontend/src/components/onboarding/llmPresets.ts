/**
 * Shared LLM provider presets and configuration helper.
 *
 * Used by both SetupPage (single-page settings) and OnboardingPage (wizard)
 * so the provider definitions and save logic stay in one place.
 */

import {
  updateLLMSettings,
  type LLMSettings,
} from "@/services/llmSettingsApi";

export type ProviderPreset = "gemini" | "openai" | "ollama" | "openrouter" | "custom";

export interface PresetConfig {
  label: string;
  provider: string;
  base_url: string | null;
  needsApiKey: boolean;
  needsBaseUrl: boolean;
  modelPlaceholder: string;
  description: string;
}

export const PRESETS: Record<ProviderPreset, PresetConfig> = {
  gemini: {
    label: "Google Gemini",
    provider: "gemini",
    base_url: null,
    needsApiKey: true,
    needsBaseUrl: false,
    modelPlaceholder: "gemini-2.5-flash",
    description: "Google's Gemini models. Requires a Gemini API key.",
  },
  openai: {
    label: "OpenAI",
    provider: "openai_compatible",
    base_url: "https://api.openai.com/v1",
    needsApiKey: true,
    needsBaseUrl: false,
    modelPlaceholder: "gpt-4.1-mini",
    description: "OpenAI's GPT models. Requires an OpenAI API key.",
  },
  ollama: {
    label: "Ollama (Local)",
    provider: "openai_compatible",
    base_url: "http://localhost:11434/v1",
    needsApiKey: false,
    needsBaseUrl: true,
    modelPlaceholder: "Pull a model with: ollama pull <model-name>",
    description: "Run models locally with Ollama. No API key needed. Start with `ollama serve`.",
  },
  openrouter: {
    label: "OpenRouter",
    provider: "openai_compatible",
    base_url: "https://openrouter.ai/api/v1",
    needsApiKey: true,
    needsBaseUrl: false,
    modelPlaceholder: "e.g. anthropic/claude-3.5-sonnet",
    description: "Access multiple providers through OpenRouter. Requires an OpenRouter API key.",
  },
  custom: {
    label: "Custom (OpenAI-compatible)",
    provider: "openai_compatible",
    base_url: "",
    needsApiKey: true,
    needsBaseUrl: true,
    modelPlaceholder: "Model name",
    description: "Any provider that exposes the OpenAI Chat Completions API.",
  },
};

/**
 * Mutable form state shared across the provider / credentials wizard steps.
 */
export interface LlmFormState {
  preset: ProviderPreset;
  apiKey: string;
  baseUrl: string;
  modelMain: string;
}

/**
 * Resolve the active preset key from loaded LLM settings (best-effort match
 * by base_url / provider). Falls back to "gemini".
 */
export function presetFromSettings(settings: LLMSettings | null): ProviderPreset {
  if (!settings) return "gemini";
  if (settings.provider === "gemini") return "gemini";
  const base = settings.base_url ?? "";
  // Parse the URL and check the hostname (and port for Ollama) rather than
  // using substring matching, which can be fooled by hosts like
  // "openai.com.evil.com" or "evil.com/openai.com".
  let host = "";
  let port = "";
  try {
    // Add a protocol if missing so URL() parses the host correctly.
    const parsed = new URL(base.includes("://") ? base : `http://${base}`);
    host = parsed.hostname.toLowerCase();
    port = parsed.port;
  } catch {
    // Malformed URL — fall through to "custom" below.
  }
  if (host === "api.openai.com") return "openai";
  if (
    (host === "localhost" || host === "127.0.0.1") &&
    port === "11434"
  ) {
    return "ollama";
  }
  if (host === "openrouter.ai") return "openrouter";
  if (settings.provider === "openai_compatible") return "custom";
  return "gemini";
}

/**
 * Validate the LLM form and persist it via the settings API.
 *
 * Returns the updated LLMSettings on success. Throws an Error with a
 * user-facing message when validation fails (so callers can surface it).
 *
 * @param form      Current form state from the wizard.
 * @param settings  Currently loaded settings (used to detect existing keys).
 */
export async function saveLlmForm(
  form: LlmFormState,
  settings: LLMSettings | null,
): Promise<LLMSettings> {
  const config = PRESETS[form.preset];

  if (config.needsApiKey && !form.apiKey && !settings?.has_api_key) {
    throw new Error("API key is required for this provider.");
  }

  if (config.provider === "openai_compatible" && !form.baseUrl) {
    throw new Error("Base URL is required for OpenAI-compatible providers.");
  }

  if (!form.modelMain) {
    throw new Error("Model name is required.");
  }

  // For Ollama, use a dummy key (required by SDK but ignored by Ollama).
  // When needsApiKey is true and the user left the field blank, send undefined
  // so the backend preserves the existing key.
  const effectiveApiKey = config.needsApiKey
    ? form.apiKey || undefined
    : "ollama";

  return updateLLMSettings({
    provider: config.provider,
    api_key: effectiveApiKey,
    base_url: config.provider === "gemini" ? undefined : form.baseUrl,
    model_main: form.modelMain,
    model_lite: form.modelMain, // Use same model for lite tasks
  });
}
