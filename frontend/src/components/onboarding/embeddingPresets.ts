/**
 * Shared embedding provider presets.
 *
 * Used by both the onboarding EmbeddingsStep and the SettingsDialog so
 * provider labels, descriptions, and signup URLs stay in sync.
 */

export type EmbeddingProvider = "voyage" | "cohere" | "ollama" | "openai";

export interface EmbeddingPreset {
  label: string;
  description: string;
  needsApiKey: boolean;
  defaultModel: string;
  defaultDim: number;
  keyLabel: string;
  keyPlaceholder: string;
  signupUrl: string;
}

export const EMBEDDING_PRESETS: Record<EmbeddingProvider, EmbeddingPreset> = {
  voyage: {
    label: "Voyage AI",
    description: "Best quality embeddings for RAG. Free tier available.",
    needsApiKey: true,
    defaultModel: "voyage-4-lite",
    defaultDim: 1024,
    keyLabel: "Voyage API Key",
    keyPlaceholder: "pa-xxxxxxxxxxxxxxxxxxxxxxxx",
    signupUrl: "https://dashboard.voyageai.com/",
  },
  cohere: {
    label: "Cohere",
    description: "embed-english-v3, 1024d. Free trial keys available.",
    needsApiKey: true,
    defaultModel: "embed-english-v3",
    defaultDim: 1024,
    keyLabel: "Cohere API Key",
    keyPlaceholder: "xxxxxxxxxxxxxxxxxxxxxxxxxx",
    signupUrl: "https://dashboard.cohere.com/api-keys",
  },
  ollama: {
    label: "Ollama (local)",
    description: "Run embeddings locally with bge-large-en-v1.5. No API key needed.",
    needsApiKey: false,
    defaultModel: "bge-large-en-v1.5",
    defaultDim: 1024,
    keyLabel: "",
    keyPlaceholder: "",
    signupUrl: "",
  },
  openai: {
    label: "OpenAI",
    description: "text-embedding-3-small (truncated to 1024d). Uses your OpenAI key.",
    needsApiKey: true,
    defaultModel: "text-embedding-3-small",
    defaultDim: 1024,
    keyLabel: "OpenAI API Key",
    keyPlaceholder: "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
    signupUrl: "https://platform.openai.com/api-keys",
  },
};
