import { useState, useEffect, useCallback, useRef } from "react";
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
 // Skip the modelMain reset on the initial settings load so the user's
 // actual configured model isn't replaced with the preset default.
 const skipModelResetRef = useRef(true);

 const fetchSettings = useCallback(async () => {
 try {
 const [s, status] = await Promise.all([getLLMSettings(), getConfigStatus().catch(() => null)]);
 setSettings(s);
 setConfigStatus(status);
 skipModelResetRef.current = true;
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

 // When preset changes, update base_url and reset model to the preset's
 // recommended default. Prevents a stale model from the previous provider
 // from being saved under the new provider. Skipped on initial load so the
 // user's actual configured model is preserved.
 useEffect(() => {
 const config = PRESETS[preset];
 if (config.base_url !== null) {
 setBaseUrl(config.base_url);
 }
 if (skipModelResetRef.current) {
 skipModelResetRef.current = false;
 return; // Initial load: keep the loaded model.
 }
 setModelMain(config.defaultModel);
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
 <div className="animate-pulse text-text-muted font-inter text-sm 3xl:text-base 4xl:text-lg">Loading...</div>
 </div>
 );
 }

 if (success) {
 return (
 <div className="min-h-screen bg-surface-base flex items-center justify-center px-6">
 <div className="text-center max-w-md 3xl:max-w-lg 4xl:max-w-xl">
 <div className="text-5xl 3xl:text-6xl 4xl:text-7xl mb-4">&#10003;</div>
 <h1 className="text-2xl 3xl:text-3xl 4xl:text-4xl font-poppins font-semibold text-text-primary mb-2">
 Settings Saved
 </h1>
 <p className="text-text-muted font-inter text-sm 3xl:text-base 4xl:text-lg">
 Redirecting you to the chat...
 </p>
 </div>
 </div>
 );
 }

 const config = PRESETS[preset];

 return (
 <div className="min-h-screen bg-surface-base flex items-center justify-center px-6 3xl:px-8 4xl:px-10 py-12 3xl:py-16 4xl:py-20">
 <div className="w-full max-w-2xl 3xl:max-w-3xl 4xl:max-w-4xl">
 <div className="mb-8 3xl:mb-10 4xl:mb-12">
 <h1 className="text-3xl 3xl:text-4xl 4xl:text-5xl font-poppins font-bold text-text-primary mb-2">
 {settings?.is_configured ? "LLM Settings" : "Welcome to Cora"}
 </h1>
 <p className="text-text-muted font-inter text-sm 3xl:text-base 4xl:text-lg">
 {settings?.is_configured
 ? "Change your AI model provider and settings."
 : "Choose your AI provider to get started. You can change this later."}
 </p>
 {!settings?.is_configured && (
 <p className="mt-3 text-xs 3xl:text-sm 4xl:text-base font-inter">
 <Link to="/onboarding/" className="text-brand-700 underline hover:text-brand-hover">
 Prefer a guided setup? Try the onboarding wizard &rarr;
 </Link>
 </p>
 )}
 </div>

 {/* Provider presets */}
 <div className="mb-6 3xl:mb-8 4xl:mb-10">
 <label className="block text-sm font-poppins font-medium text-text-primary mb-3">
 Provider
 </label>
 <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 3xl:gap-4 4xl:gap-5">
 {(Object.keys(PRESETS) as ProviderPreset[]).map((key) => (
 <button
 key={key}
 type="button"
 onClick={() => setPreset(key)}
 className={`px-4 3xl:px-5 py-3 3xl:py-4 4xl:py-5 rounded-lg border-2 text-sm font-poppins font-medium transition-all ${
 preset === key
 ? "border-brand-700 bg-brand-50 text-brand-700"
 : "border-border-ui bg-surface-card text-text-secondary hover:border-brand-300"
 }`}
 >
 {PRESETS[key].label}
 </button>
 ))}
 </div>
 <p className="mt-2 text-xs 3xl:text-sm 4xl:text-base text-text-muted font-inter">{config.description}</p>
 </div>

 {/* API Key */}
 {config.needsApiKey && (
 <div className="mb-6 3xl:mb-8 4xl:mb-10">
 <label className="block text-sm font-poppins font-medium text-text-primary mb-2">
 API Key
 {settings?.has_api_key && (
 <span className="ml-2 text-xs 3xl:text-sm 4xl:text-base text-semantic-success-text font-normal">
 (already set — leave blank to keep existing)
 </span>
 )}
 </label>
 <input
 type="password"
 value={apiKey}
 onChange={(e) => setApiKey(e.target.value)}
 placeholder={settings?.has_api_key ? "••••••••••••" : "Enter your API key"}
 className="w-full px-4 3xl:px-5 py-3 3xl:py-4 4xl:py-5 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-sm 3xl:text-base 4xl:text-lg focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-focus"
 />
 </div>
 )}

 {/* Base URL */}
 {config.needsBaseUrl && (
 <div className="mb-6 3xl:mb-8 4xl:mb-10">
 <label className="block text-sm font-poppins font-medium text-text-primary mb-2">
 Base URL
 </label>
 <input
 type="text"
 value={baseUrl}
 onChange={(e) => setBaseUrl(e.target.value)}
 placeholder="https://api.example.com/v1"
 className="w-full px-4 3xl:px-5 py-3 3xl:py-4 4xl:py-5 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-sm 3xl:text-base 4xl:text-lg focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-focus"
 />
 </div>
 )}

 {/* Model selection */}
 <div className="mb-6 3xl:mb-8 4xl:mb-10">
 <label className="block text-sm font-poppins font-medium text-text-primary mb-2">
 Model
 </label>
 {preset === "ollama" && ollamaModels.length > 0 ? (
 <select
 value={modelMain}
 onChange={(e) => setModelMain(e.target.value)}
 className="w-full px-4 3xl:px-5 py-3 3xl:py-4 4xl:py-5 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-sm 3xl:text-base 4xl:text-lg focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-focus"
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
 className="w-full px-4 3xl:px-5 py-3 3xl:py-4 4xl:py-5 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-sm 3xl:text-base 4xl:text-lg focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-focus"
 />
 )}
 {preset === "ollama" && ollamaModels.length === 0 && !loadingModels && (
 <p className="mt-2 text-xs 3xl:text-sm 4xl:text-base text-semantic-warning-text font-inter">
 No models found. Make sure Ollama is running (`ollama serve`) and you've pulled a model
 (`ollama pull &lt;model-name&gt;`). You can also enter the model name manually above.
 </p>
 )}
 </div>

 {/* Error */}
 {error && (
 <div className="mb-6 3xl:mb-8 4xl:mb-10 p-4 3xl:p-5 4xl:p-6 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-sm 3xl:text-base 4xl:text-lg">
 {error}
 </div>
 )}

 {/* Actions */}
 <div className="flex gap-3 3xl:gap-4 4xl:gap-5">
 <button
 type="button"
 onClick={() => void handleSave()}
 disabled={saving}
 className="px-6 3xl:px-8 py-3 3xl:py-4 4xl:py-5 rounded-lg bg-brand-700 text-white font-poppins text-sm 3xl:text-base 4xl:text-lg font-semibold shadow-md transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-focus"
 >
 {saving ? "Saving..." : settings?.is_configured ? "Update Settings" : "Save & Continue"}
 </button>
 {settings?.is_configured && (
 <button
 type="button"
 onClick={() => navigate("/")}
 className="px-6 3xl:px-8 py-3 3xl:py-4 4xl:py-5 rounded-lg border border-border-ui text-text-secondary font-poppins text-sm 3xl:text-base 4xl:text-lg font-medium transition-colors hover:bg-surface-card"
 >
 Cancel
 </button>
 )}
 </div>

 {/* Note about restart */}
 <p className="mt-6 3xl:mt-8 4xl:mt-10 text-xs 3xl:text-sm 4xl:text-base text-text-muted font-inter">
 Note: After changing the provider, the backend needs to restart for the new client to take
 effect.
 </p>

 {/* Full configuration status */}
 {configStatus && (
 <div className="mt-8 3xl:mt-10 4xl:mt-12 border-t border-border-ui pt-6">
 <h2 className="text-lg font-poppins font-semibold text-text-primary mb-4">
 Configuration Status
 </h2>

 {/* Overall readiness */}
 <div className={`p-3 3xl:p-4 4xl:p-5 rounded-lg mb-4 text-sm font-inter ${
 configStatus.ready
 ? "bg-semantic-success-bg text-semantic-success-text"
 : "bg-semantic-warning-bg text-semantic-warning-text"
 }`}>
 {configStatus.ready
 ? "\u2713 All providers configured. Cora is ready."
 : "\u26A0 Some providers are not configured. See below."}
 </div>

 {/* Provider status grid */}
 <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 3xl:gap-4 4xl:gap-5 mb-4">
 <ProviderStatusCard label="LLM" status={configStatus.llm} />
 <ProviderStatusCard label="Embeddings" status={configStatus.embeddings} />
 <ProviderStatusCard label="Reranker" status={configStatus.reranker} />
 <ProviderStatusCard label="Web Search" status={configStatus.search} />
 </div>

 {/* Qdrant info */}
 {configStatus.qdrant && (
 <div className="p-3 3xl:p-4 4xl:p-5 rounded-lg bg-surface-card border border-border-ui mb-4">
 <div className="text-sm font-poppins font-medium text-text-primary mb-1">Qdrant</div>
 {configStatus.qdrant.error ? (
 <div className="text-xs 3xl:text-sm 4xl:text-base text-semantic-error-text font-inter">
 Connection error: {configStatus.qdrant.error}
 </div>
 ) : (
 <div className="text-xs 3xl:text-sm 4xl:text-base text-text-muted font-inter">
 Collection: {configStatus.qdrant.collection} &middot; Vectors: {configStatus.qdrant.vector_dim}d &middot; Points: {configStatus.qdrant.points_count?.toLocaleString() ?? "unknown"}
 </div>
 )}
 </div>
 )}

 {/* Warnings */}
 {configStatus.warnings.length > 0 && (
 <div className="space-y-2">
 {configStatus.warnings.map((w, i) => (
 <div key={i} className="p-3 3xl:p-4 4xl:p-5 rounded-lg bg-semantic-warning-bg border border-semantic-warning-border text-semantic-warning-text font-inter text-xs 3xl:text-sm 4xl:text-base">
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
 <div className={`p-3 3xl:p-4 4xl:p-5 rounded-lg border ${ok ? "border-semantic-success-border bg-semantic-success-bg" : "border-semantic-warning-border bg-semantic-warning-bg"}`}>
 <div className="flex items-center justify-between mb-1">
 <span className="text-sm font-poppins font-medium text-text-primary">{label}</span>
 <span className={`text-xs 3xl:text-sm 4xl:text-base font-inter ${ok ? "text-semantic-success-text" : "text-semantic-warning-text"}`}>
 {ok ? "\u2713 Ready" : "\u26A0 Incomplete"}
 </span>
 </div>
 <div className="text-xs 3xl:text-sm 4xl:text-base text-text-muted font-inter">
 {status.provider === "none" ? "Disabled" : status.provider}
 {status.model && status.provider !== "none" ? ` \u00B7 ${status.model}` : ""}
 </div>
 {status.warning && (
 <div className="text-xs 3xl:text-sm 4xl:text-base text-semantic-warning-text font-inter mt-1">{status.warning}</div>
 )}
 </div>
 );
}

export default SetupPage;
