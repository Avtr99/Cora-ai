import { useState, useEffect, useCallback } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  getLLMSettings,
  listLLMModels,
  getConfigStatus,
  type LLMSettings,
  type LLMModel,
  type ConfigStatus,
} from "@/services/llmSettingsApi";
import {
  PRESETS,
  presetFromSettings,
  saveLlmForm,
  type ProviderPreset,
} from "@/components/onboarding/llmPresets";

const SetupPage = (): JSX.Element => {
  const navigate = useNavigate();
  const [settings, setSettings] = useState<LLMSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  // Form state
  const [preset, setPreset] = useState<ProviderPreset>("gemini");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [modelMain, setModelMain] = useState("");
  const [ollamaModels, setOllamaModels] = useState<LLMModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [configStatus, setConfigStatus] = useState<ConfigStatus | null>(null);

  const fetchSettings = useCallback(async () => {
    try {
      const [s, status] = await Promise.all([getLLMSettings(), getConfigStatus().catch(() => null)]);
      setSettings(s);
      setConfigStatus(status);
      setPreset(presetFromSettings(s));
      if (s.base_url) setBaseUrl(s.base_url);
      if (s.model_main) setModelMain(s.model_main);
    } catch (e) {
      setError(`Failed to load settings: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchSettings();
  }, [fetchSettings]);

  // When preset changes, update base_url
  useEffect(() => {
    const config = PRESETS[preset];
    if (config.base_url !== null) {
      setBaseUrl(config.base_url);
    }
  }, [preset]);

  // Fetch Ollama models when preset is ollama
  useEffect(() => {
    if (preset !== "ollama") {
      setOllamaModels([]);
      return;
    }
    const url = baseUrl || "http://localhost:11434/v1";
    setLoadingModels(true);
    listLLMModels(url.replace("/v1", ""))
      .then(setOllamaModels)
      .catch(() => setOllamaModels([]))
      .finally(() => setLoadingModels(false));
  }, [preset, baseUrl]);

  const handleSave = async (): Promise<void> => {
    setError(null);
    setSaving(true);

    try {
      await saveLlmForm({ preset, apiKey, baseUrl, modelMain }, settings);
      setSuccess(true);
      // Redirect to home after a short delay
      setTimeout(() => navigate("/"), 2000);
    } catch (e) {
      setError(`Failed to save settings: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-base flex items-center justify-center">
        <div className="animate-pulse text-text-muted font-inter text-sm">Loading...</div>
      </div>
    );
  }

  if (success) {
    return (
      <div className="min-h-screen bg-surface-base flex items-center justify-center px-6">
        <div className="text-center max-w-md">
          <div className="text-5xl mb-4">&#10003;</div>
          <h1 className="text-2xl font-poppins font-semibold text-text-primary mb-2">
            Settings Saved
          </h1>
          <p className="text-text-muted font-inter text-sm">
            Redirecting you to the chat...
          </p>
        </div>
      </div>
    );
  }

  const config = PRESETS[preset];

  return (
    <div className="min-h-screen bg-surface-base flex items-center justify-center px-6 py-12">
      <div className="w-full max-w-2xl">
        <div className="mb-8">
          <h1 className="text-3xl font-poppins font-bold text-text-primary mb-2">
            {settings?.is_configured ? "LLM Settings" : "Welcome to Cora"}
          </h1>
          <p className="text-text-muted font-inter text-sm">
            {settings?.is_configured
              ? "Change your AI model provider and settings."
              : "Choose your AI provider to get started. You can change this later."}
          </p>
          {!settings?.is_configured && (
            <p className="mt-3 text-xs font-inter">
              <Link to="/onboarding/" className="text-brand-700 underline hover:text-brand-hover">
                Prefer a guided setup? Try the onboarding wizard &rarr;
              </Link>
            </p>
          )}
        </div>

        {/* Provider presets */}
        <div className="mb-6">
          <label className="block text-sm font-poppins font-medium text-text-primary mb-3">
            Provider
          </label>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {(Object.keys(PRESETS) as ProviderPreset[]).map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setPreset(key)}
                className={`px-4 py-3 rounded-lg border-2 text-sm font-poppins font-medium transition-all ${
                  preset === key
                    ? "border-brand-700 bg-brand-50 text-brand-700"
                    : "border-border-default bg-surface-elevated text-text-secondary hover:border-brand-300"
                }`}
              >
                {PRESETS[key].label}
              </button>
            ))}
          </div>
          <p className="mt-2 text-xs text-text-muted font-inter">{config.description}</p>
        </div>

        {/* API Key */}
        {config.needsApiKey && (
          <div className="mb-6">
            <label className="block text-sm font-poppins font-medium text-text-primary mb-2">
              API Key
              {settings?.has_api_key && (
                <span className="ml-2 text-xs text-success font-normal">
                  (already set — leave blank to keep existing)
                </span>
              )}
            </label>
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder={settings?.has_api_key ? "••••••••••••" : "Enter your API key"}
              className="w-full px-4 py-3 rounded-lg border border-border-default bg-surface-elevated text-text-primary font-inter text-sm focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </div>
        )}

        {/* Base URL */}
        {config.needsBaseUrl && (
          <div className="mb-6">
            <label className="block text-sm font-poppins font-medium text-text-primary mb-2">
              Base URL
            </label>
            <input
              type="text"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              placeholder="https://api.example.com/v1"
              className="w-full px-4 py-3 rounded-lg border border-border-default bg-surface-elevated text-text-primary font-inter text-sm focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          </div>
        )}

        {/* Model selection */}
        <div className="mb-6">
          <label className="block text-sm font-poppins font-medium text-text-primary mb-2">
            Model
          </label>
          {preset === "ollama" && ollamaModels.length > 0 ? (
            <select
              value={modelMain}
              onChange={(e) => setModelMain(e.target.value)}
              className="w-full px-4 py-3 rounded-lg border border-border-default bg-surface-elevated text-text-primary font-inter text-sm focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              <option value="">Select a model...</option>
              {ollamaModels.map((m) => (
                <option key={m.name} value={m.name}>
                  {m.name}
                  {m.parameter_size ? ` (${m.parameter_size})` : ""}
                  {m.family ? ` — ${m.family}` : ""}
                </option>
              ))}
            </select>
          ) : preset === "ollama" && loadingModels ? (
            <div className="text-sm text-text-muted font-inter">Loading available models...</div>
          ) : (
            <input
              type="text"
              value={modelMain}
              onChange={(e) => setModelMain(e.target.value)}
              placeholder={config.modelPlaceholder}
              className="w-full px-4 py-3 rounded-lg border border-border-default bg-surface-elevated text-text-primary font-inter text-sm focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200"
            />
          )}
          {preset === "ollama" && ollamaModels.length === 0 && !loadingModels && (
            <p className="mt-2 text-xs text-warning font-inter">
              No models found. Make sure Ollama is running (`ollama serve`) and you've pulled a model
              (`ollama pull &lt;model-name&gt;`). You can also enter the model name manually above.
            </p>
          )}
        </div>

        {/* Error */}
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-error/10 border border-error/30 text-error font-inter text-sm">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="px-6 py-3 rounded-lg bg-brand-700 text-white font-poppins text-sm font-semibold shadow-md transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500"
          >
            {saving ? "Saving..." : settings?.is_configured ? "Update Settings" : "Save & Continue"}
          </button>
          {settings?.is_configured && (
            <button
              type="button"
              onClick={() => navigate("/")}
              className="px-6 py-3 rounded-lg border border-border-default text-text-secondary font-poppins text-sm font-medium transition-colors hover:bg-surface-elevated"
            >
              Cancel
            </button>
          )}
        </div>

        {/* Note about restart */}
        <p className="mt-6 text-xs text-text-muted font-inter">
          Note: After changing the provider, the backend needs to restart for the new client to take
          effect.
        </p>

        {/* Full configuration status */}
        {configStatus && (
          <div className="mt-8 border-t border-border-default pt-6">
            <h2 className="text-lg font-poppins font-semibold text-text-primary mb-4">
              Configuration Status
            </h2>

            {/* Overall readiness */}
            <div className={`p-3 rounded-lg mb-4 text-sm font-inter ${
              configStatus.ready
                ? "bg-success/10 text-success"
                : "bg-warning/10 text-warning"
            }`}>
              {configStatus.ready
                ? "\u2713 All providers configured. Cora is ready."
                : "\u26A0 Some providers are not configured. See below."}
            </div>

            {/* Provider status grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-4">
              <ProviderStatusCard label="LLM" status={configStatus.llm} />
              <ProviderStatusCard label="Embeddings" status={configStatus.embeddings} />
              <ProviderStatusCard label="Reranker" status={configStatus.reranker} />
              <ProviderStatusCard label="Web Search" status={configStatus.search} />
            </div>

            {/* Qdrant info */}
            {configStatus.qdrant && (
              <div className="p-3 rounded-lg bg-surface-elevated border border-border-default mb-4">
                <div className="text-sm font-poppins font-medium text-text-primary mb-1">Qdrant</div>
                {configStatus.qdrant.error ? (
                  <div className="text-xs text-error font-inter">
                    Connection error: {configStatus.qdrant.error}
                  </div>
                ) : (
                  <div className="text-xs text-text-muted font-inter">
                    Collection: {configStatus.qdrant.collection} &middot; Vectors: {configStatus.qdrant.vector_dim}d &middot; Points: {configStatus.qdrant.points_count?.toLocaleString() ?? "unknown"}
                  </div>
                )}
              </div>
            )}

            {/* Warnings */}
            {configStatus.warnings.length > 0 && (
              <div className="space-y-2">
                {configStatus.warnings.map((w, i) => (
                  <div key={i} className="p-3 rounded-lg bg-warning/10 border border-warning/30 text-warning font-inter text-xs">
                    {w}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

/** Compact status card for a single provider. */
function ProviderStatusCard({ label, status }: { label: string; status: { provider: string; has_api_key: boolean; model: string | null; is_configured: boolean; warning: string | null } }): JSX.Element {
  const ok = status.is_configured;
  return (
    <div className={`p-3 rounded-lg border ${ok ? "border-success/30 bg-success/5" : "border-warning/30 bg-warning/5"}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-poppins font-medium text-text-primary">{label}</span>
        <span className={`text-xs font-inter ${ok ? "text-success" : "text-warning"}`}>
          {ok ? "\u2713 Ready" : "\u26A0 Incomplete"}
        </span>
      </div>
      <div className="text-xs text-text-muted font-inter">
        {status.provider === "none" ? "Disabled" : status.provider}
        {status.model && status.provider !== "none" ? ` \u00B7 ${status.model}` : ""}
      </div>
      {status.warning && (
        <div className="text-xs text-warning font-inter mt-1">{status.warning}</div>
      )}
    </div>
  );
}

export default SetupPage;
