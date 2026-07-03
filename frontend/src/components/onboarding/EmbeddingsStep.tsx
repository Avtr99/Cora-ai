/**
 * EmbeddingsStep — choose embedding provider + enter API key.
 *
 * Embeddings are used by Qdrant to search the document store. The provider
 * must match the dimension of the existing Qdrant collection (default 1024d).
 */

import { useEffect, useState } from "react";
import {
  getEmbeddingSettings,
  updateEmbeddingSettings,
  type EmbeddingSettings,
} from "@/services/llmSettingsApi";
import { StepHeading, StepActions } from "@/components/onboarding/ProviderStep";
import {
  EMBEDDING_PRESETS,
  type EmbeddingProvider,
} from "@/components/onboarding/embeddingPresets";
import { Field, ErrorBox, inputClass } from "@/components/settings/settingsPrimitives";

interface EmbeddingsStepProps {
  onBack: () => void;
  onContinue: () => void;
}

const EmbeddingsStep = ({ onBack, onContinue }: EmbeddingsStepProps): JSX.Element => {
  const [provider, setProvider] = useState<EmbeddingProvider>("voyage");
  const [apiKey, setApiKey] = useState("");
  const [ollamaUrl, setOllamaUrl] = useState("http://localhost:11434");
  const [existing, setExisting] = useState<EmbeddingSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEmbeddingSettings()
      .then((s) => {
        if (cancelled) return;
        setExisting(s);
        setProvider(s.provider as EmbeddingProvider);
        if (s.provider === "ollama" && s.ollama_base_url) {
          setOllamaUrl(s.ollama_base_url);
        }
      })
      .catch(() => { /* backend down — defaults are fine */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const config = EMBEDDING_PRESETS[provider];

  const handleSave = async (): Promise<void> => {
    setError(null);
    setSaving(true);
    try {
      await updateEmbeddingSettings({
        provider,
        api_key: apiKey || undefined,
        ollama_base_url: provider === "ollama" ? ollamaUrl : undefined,
      });
      onContinue();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="py-8 text-center text-text-muted font-inter text-sm animate-pulse">
        Loading embedding settings...
      </div>
    );
  }

  return (
    <div>
      <StepHeading
        title="Set up embeddings"
        subtitle="Embeddings power document search. Pick a provider — Voyage AI is recommended for best RAG quality."
      />

      {/* Provider selection */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
        {(Object.keys(EMBEDDING_PRESETS) as EmbeddingProvider[]).map((key) => {
          const isActive = provider === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => setProvider(key)}
              className={`px-3 py-2.5 rounded-lg border-2 text-xs font-poppins font-medium transition-all ${
                isActive
                  ? "border-brand-700 bg-brand-100 text-brand-700"
                  : "border-border-ui bg-surface-card text-text-secondary hover:border-brand-200"
              }`}
            >
              {EMBEDDING_PRESETS[key].label}
            </button>
          );
        })}
      </div>

      <p className="text-xs text-text-muted font-inter mb-5">{config.description}</p>

      {/* API key (if needed) */}
      {config.needsApiKey && (
        <div className="mb-5">
          <Field
            label={config.keyLabel}
            hint={existing?.has_api_key ? "(already set — leave blank to keep)" : undefined}
          >
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={existing?.has_api_key ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" : config.keyPlaceholder}
              className={inputClass}
            />
            <a
              href={config.signupUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block mt-1.5 text-xs text-brand-700 hover:text-brand-hover font-inter"
            >
              Get a key &rarr;
            </a>
          </Field>
        </div>
      )}

      {/* Ollama base URL */}
      {provider === "ollama" && (
        <div className="mb-5">
          <Field label="Ollama Base URL">
            <input
              type="text"
              value={ollamaUrl}
              onChange={(e) => setOllamaUrl(e.target.value)}
              placeholder="http://localhost:11434"
              className={inputClass}
            />
            <p className="mt-1.5 text-xs text-text-muted font-inter">
              Pull the model first: <code>ollama pull bge-large-en-v1.5</code>
            </p>
          </Field>
        </div>
      )}

      {/* Dimension note */}
      <div className="mb-5 p-3 rounded-lg bg-surface-subtle border border-border-ui">
        <p className="text-xs text-text-muted font-inter">
          <strong className="text-text-primary">Dimension:</strong> {config.defaultDim}d
          {existing && existing.dim !== config.defaultDim && (
            <span className="ml-1 text-semantic-warning-icon">
              {"\u26A0"} Your Qdrant collection uses {existing.dim}d. Switching to a model with a
              different dimension requires re-ingesting documents.
            </span>
          )}
          {" "}— must match your Qdrant collection vector size.
        </p>
      </div>

      {error && <div className="mb-5"><ErrorBox message={error} /></div>}

      <StepActions
        onBack={onBack}
        onContinue={() => void handleSave()}
        continueLabel="Save & continue"
        saving={saving}
      />
    </div>
  );
};

export default EmbeddingsStep;
