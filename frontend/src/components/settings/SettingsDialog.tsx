/**
 * SettingsDialog — modal for configuring all Cora providers from within the chat.
 *
 * Tabbed interface:
 *   - AI Model tab:   provider + API key + model + test connection
 *   - Embeddings tab: provider + API key (powers document search)
 *   - Search tab:     Tavily web search or disable
 *
 * Also shows a compact config-status summary at the bottom.
 */

import { useCallback, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useSettingsDialogStore } from "@/store/settingsDialogStore";
import {
  getLLMSettings,
  getConfigStatus,
  testLLMConnection,
  updateEmbeddingSettings,
  updateSearchSettings,
  getEmbeddingSettings,
  getSearchSettings,
  type LLMSettings,
  type LLMTestResult,
  type ConfigStatus,
  type ProviderStatus,
  type EmbeddingSettings,
  type SearchSettings,
} from "@/services/llmSettingsApi";
import {
  PRESETS,
  presetFromSettings,
  saveLlmForm,
  type LlmFormState,
} from "@/components/onboarding/llmPresets";
import {
  EMBEDDING_PRESETS,
  type EmbeddingProvider,
} from "@/components/onboarding/embeddingPresets";
import {
  Field,
  ProviderGrid,
  TestConnection,
  ErrorBox,
  SaveCancel,
  SavedBanner,
  inputClass,
  type TestState,
} from "@/components/settings/settingsPrimitives";

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved?: () => void;
}

type Tab = "llm" | "embeddings" | "search";

const SettingsDialog = ({ open, onOpenChange, onSaved }: SettingsDialogProps): JSX.Element => {
  const queryClient = useQueryClient();
  const tab = useSettingsDialogStore((s) => s.tab);
  const setTab = useSettingsDialogStore((s) => s.setTab);

  const refreshChatReadiness = useCallback(async () => {
    // Invalidate the chat readiness config status so the banner/composer update
    // immediately after the user changes providers (especially web search).
    await queryClient.invalidateQueries({ queryKey: ['chat-readiness', 'config-status'] });
    // Also refresh the dialog's own system status summary.
    try {
      const status = await getConfigStatus();
      setConfigStatus(status);
    } catch {
      // Non-critical: the dialog status summary can stay stale briefly.
    }
  }, [queryClient]);

  // LLM tab state
  const [llmSettings, setLlmSettings] = useState<LLMSettings | null>(null);
  const [llmForm, setLlmForm] = useState<LlmFormState>({
    preset: "gemini",
    apiKey: "",
    baseUrl: "",
    modelMain: "",
  });
  const [llmSaving, setLlmSaving] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);
  const [llmSaved, setLlmSaved] = useState(false);
  const [testState, setTestState] = useState<TestState>("idle");
  const [testResult, setTestResult] = useState<LLMTestResult | null>(null);

  // Embeddings tab state
  const [embSettings, setEmbSettings] = useState<EmbeddingSettings | null>(null);
  const [embProvider, setEmbProvider] = useState<EmbeddingProvider>("voyage");
  const [embApiKey, setEmbApiKey] = useState("");
  const [embOllamaUrl, setEmbOllamaUrl] = useState("http://localhost:11434");
  const [embSaving, setEmbSaving] = useState(false);
  const [embError, setEmbError] = useState<string | null>(null);
  const [embSaved, setEmbSaved] = useState(false);

  // Search tab state
  const [searchSettings, setSearchSettings] = useState<SearchSettings | null>(null);
  const [searchProvider, setSearchProvider] = useState("tavily");
  const [searchApiKey, setSearchApiKey] = useState("");
  const [searchSaving, setSearchSaving] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchSaved, setSearchSaved] = useState(false);

  const [configStatus, setConfigStatus] = useState<ConfigStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const patchLlmForm = useCallback((patch: Partial<LlmFormState>) => {
    setLlmForm((prev) => ({ ...prev, ...patch }));
  }, []);

  // Load all settings when dialog opens
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([
      getLLMSettings().catch(() => null),
      getEmbeddingSettings().catch(() => null),
      getSearchSettings().catch(() => null),
      getConfigStatus().catch(() => null),
    ]).then(([llm, emb, search, status]) => {
      if (cancelled) return;
      if (llm) {
        setLlmSettings(llm);
        const detected = presetFromSettings(llm);
        setLlmForm({
          preset: detected,
          apiKey: "",
          baseUrl: llm.base_url ?? PRESETS[detected].base_url ?? "",
          modelMain: llm.model_main ?? "",
        });
      }
      if (emb) {
        setEmbSettings(emb);
        setEmbProvider(emb.provider as EmbeddingProvider);
        if (emb.ollama_base_url) setEmbOllamaUrl(emb.ollama_base_url);
      }
      if (search) {
        setSearchSettings(search);
        setSearchProvider(search.provider);
      }
      setConfigStatus(status);
      setLlmSaved(false); setLlmError(null); setTestState("idle"); setTestResult(null);
      setEmbSaved(false); setEmbError(null);
      setSearchSaved(false); setSearchError(null);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [open]);

  // Update base_url when LLM preset changes
  useEffect(() => {
    setLlmForm((prev) => {
      const config = PRESETS[prev.preset];
      if (config.base_url !== null) {
        return { ...prev, baseUrl: config.base_url };
      }
      return prev;
    });
  }, [llmForm.preset]);

  // Reset LLM test state when form changes
  useEffect(() => {
    setTestState("idle");
    setTestResult(null);
  }, [llmForm.apiKey, llmForm.baseUrl, llmForm.modelMain, llmForm.preset]);

  const llmConfig = PRESETS[llmForm.preset];

  const handleTestLlm = async (): Promise<void> => {
    setLlmError(null);
    setTestState("testing");
    setTestResult(null);

    if (llmConfig.needsApiKey && !llmForm.apiKey && !llmSettings?.has_api_key) {
      setTestState("failed");
      setTestResult({ success: false, message: "API key is required." });
      return;
    }
    if (llmConfig.provider === "openai_compatible" && !llmForm.baseUrl) {
      setTestState("failed");
      setTestResult({ success: false, message: "Base URL is required." });
      return;
    }
    if (!llmForm.modelMain) {
      setTestState("failed");
      setTestResult({ success: false, message: "Model name is required." });
      return;
    }

    try {
      const result = await testLLMConnection({
        provider: llmConfig.provider,
        api_key: llmForm.apiKey || undefined,
        base_url: llmConfig.provider === "gemini" ? undefined : llmForm.baseUrl,
        model_main: llmForm.modelMain,
      });
      setTestResult(result);
      setTestState(result.success ? "success" : "failed");
    } catch (e) {
      setTestResult({
        success: false,
        message: "Could not reach the backend to test. Is the Cora server running?",
        detail: e instanceof Error ? e.message : String(e),
      });
      setTestState("failed");
    }
  };

  const closeAfterSave = useCallback(() => {
    onSaved?.();
    setTimeout(() => onOpenChange(false), 1200);
  }, [onSaved, onOpenChange]);

  const handleSaveLlm = async (): Promise<void> => {
    setLlmError(null);
    setLlmSaving(true);
    try {
      await saveLlmForm(llmForm, llmSettings);
      await refreshChatReadiness();
      setLlmSaved(true);
      // Clear the API key from memory as soon as it has been submitted.
      setLlmForm((prev) => ({ ...prev, apiKey: "" }));
      closeAfterSave();
    } catch (e) {
      setLlmError(e instanceof Error ? e.message : String(e));
    } finally {
      setLlmSaving(false);
    }
  };

  const handleSaveEmb = async (): Promise<void> => {
    setEmbError(null);
    setEmbSaving(true);
    try {
      const updated = await updateEmbeddingSettings({
        provider: embProvider,
        api_key: embApiKey || undefined,
        ollama_base_url: embProvider === "ollama" ? embOllamaUrl : undefined,
      });
      setEmbSettings(updated);
      await refreshChatReadiness();
      setEmbSaved(true);
      setEmbApiKey("");
      closeAfterSave();
    } catch (e) {
      setEmbError(e instanceof Error ? e.message : String(e));
    } finally {
      setEmbSaving(false);
    }
  };

  const handleSaveSearch = async (): Promise<void> => {
    setSearchError(null);
    setSearchSaving(true);
    try {
      const updated = await updateSearchSettings({
        provider: searchProvider,
        api_key: searchApiKey || undefined,
      });
      setSearchSettings(updated);
      await refreshChatReadiness();
      setSearchSaved(true);
      setSearchApiKey("");
      closeAfterSave();
    } catch (e) {
      setSearchError(e instanceof Error ? e.message : String(e));
    } finally {
      setSearchSaving(false);
    }
  };

  const embConfig = EMBEDDING_PRESETS[embProvider];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[90vh] overflow-y-auto rounded-xl border border-border-ui bg-surface-card shadow-modal p-6">
        <DialogHeader>
          <DialogTitle className="font-poppins text-lg font-semibold text-text-primary">Settings</DialogTitle>
          <DialogDescription className="font-inter text-sm text-text-muted">
            Configure Cora&apos;s AI providers and test connections before saving.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-center text-text-muted font-inter text-sm animate-pulse">
            Loading settings...
          </div>
        ) : (
          <div className="space-y-4">
            {/* Tabs */}
            <div className="flex gap-1 border-b border-border-ui">
              {(["llm", "embeddings", "search"] as Tab[]).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setTab(t)}
                  className={`px-4 py-2 text-sm font-poppins font-medium transition-colors border-b-2 -mb-px ${
                    tab === t
                      ? "border-brand-700 text-brand-700"
                      : "border-transparent text-text-muted hover:text-text-primary"
                  }`}
                >
                  {t === "llm" ? "AI Model" : t === "embeddings" ? "Embeddings" : "Web Search"}
                </button>
              ))}
            </div>

            {/* LLM Tab */}
            {tab === "llm" && (
              <div className="space-y-3">
                {llmSaved ? (
                  <SavedBanner text="LLM settings saved. Restart the backend for the new model to take effect." />
                ) : (
                  <>
                    <ProviderGrid
                      presets={PRESETS}
                      selected={llmForm.preset}
                      onSelect={(key) => patchLlmForm({ preset: key })}
                    />
                    <p className="text-xs text-text-muted font-inter">{llmConfig.description}</p>

                    {llmConfig.needsApiKey && (
                      <Field label="API Key" hint={llmSettings?.has_api_key ? "(already set — leave blank to keep)" : undefined}>
                        <input
                          type="password"
                          value={llmForm.apiKey}
                          onChange={(e) => patchLlmForm({ apiKey: e.target.value })}
                          placeholder={llmSettings?.has_api_key ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" : "Enter your API key"}
                          className={inputClass}
                        />
                      </Field>
                    )}

                    {llmConfig.needsBaseUrl && (
                      <Field label="Base URL">
                        <input
                          type="text"
                          value={llmForm.baseUrl}
                          onChange={(e) => patchLlmForm({ baseUrl: e.target.value })}
                          placeholder="https://api.example.com/v1"
                          className={inputClass}
                        />
                      </Field>
                    )}

                    <Field label="Model">
                      <input
                        type="text"
                        value={llmForm.modelMain}
                        onChange={(e) => patchLlmForm({ modelMain: e.target.value })}
                        placeholder={llmConfig.modelPlaceholder}
                        className={inputClass}
                      />
                    </Field>

                    <TestConnection
                      state={testState}
                      result={testResult}
                      onTest={() => void handleTestLlm()}
                    />

                    {llmError && <ErrorBox message={llmError} />}

                    <SaveCancel
                      onSave={() => void handleSaveLlm()}
                      onCancel={() => onOpenChange(false)}
                      saving={llmSaving}
                      label="Save"
                    />

                    <p className="text-xs text-text-muted font-inter">
                      Note: after changing the provider, the backend needs to restart for the new
                      client to take effect.
                    </p>
                  </>
                )}
              </div>
            )}

            {/* Embeddings Tab */}
            {tab === "embeddings" && (
              <div className="space-y-3">
                {embSaved ? (
                  <SavedBanner text="Embedding settings saved. Re-ingest documents if you changed the dimension." />
                ) : (
                  <>
                    <ProviderGrid
                      presets={EMBEDDING_PRESETS}
                      selected={embProvider}
                      onSelect={setEmbProvider}
                    />
                    <p className="text-xs text-text-muted font-inter">{embConfig.description}</p>

                    {embConfig.needsApiKey && (
                      <Field
                        label={embConfig.keyLabel}
                        hint={embSettings?.has_api_key ? "(already set — leave blank to keep)" : undefined}
                      >
                        <input
                          type="password"
                          value={embApiKey}
                          onChange={(e) => setEmbApiKey(e.target.value)}
                          placeholder={embSettings?.has_api_key ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" : embConfig.keyPlaceholder}
                          className={inputClass}
                        />
                        <a
                          href={embConfig.signupUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-block mt-1.5 text-xs text-brand-700 hover:text-brand-hover font-inter"
                        >
                          Get a key &rarr;
                        </a>
                      </Field>
                    )}

                    {embProvider === "ollama" && (
                      <Field label="Ollama Base URL">
                        <input
                          type="text"
                          value={embOllamaUrl}
                          onChange={(e) => setEmbOllamaUrl(e.target.value)}
                          placeholder="http://localhost:11434"
                          className={inputClass}
                        />
                      </Field>
                    )}

                    {embSettings && (
                      <div className="p-3 rounded-lg bg-surface-subtle border border-border-ui">
                        <p className="text-xs text-text-muted font-inter">
                          <strong className="text-text-primary">Current dimension:</strong> {embSettings.dim}d
                          {" "}- must match your Qdrant collection.
                        </p>
                      </div>
                    )}

                    {embError && <ErrorBox message={embError} />}

                    <SaveCancel
                      onSave={() => void handleSaveEmb()}
                      onCancel={() => onOpenChange(false)}
                      saving={embSaving}
                    />
                  </>
                )}
              </div>
            )}

            {/* Search Tab */}
            {tab === "search" && (
              <div className="space-y-3">
                {searchSaved ? (
                  <SavedBanner text="Search settings saved." />
                ) : (
                  <>
                    <div className="grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => setSearchProvider("tavily")}
                        className={`px-4 py-3 rounded-lg border text-sm font-poppins font-medium transition-all text-left ${
                          searchProvider === "tavily"
                            ? "border-brand-700 bg-brand-50 text-brand-700"
                            : "border-border-ui bg-surface-card text-text-secondary hover:border-brand-300 hover:bg-surface-subtle"
                        }`}
                      >
                        <div className="font-semibold">Tavily</div>
                        <div className="text-xs font-normal mt-0.5 text-text-muted">AI web search</div>
                      </button>
                      <button
                        type="button"
                        onClick={() => setSearchProvider("none")}
                        className={`px-4 py-3 rounded-lg border text-sm font-poppins font-medium transition-all text-left ${
                          searchProvider === "none"
                            ? "border-brand-700 bg-brand-50 text-brand-700"
                            : "border-border-ui bg-surface-card text-text-secondary hover:border-brand-300 hover:bg-surface-subtle"
                        }`}
                      >
                        <div className="font-semibold">Disabled</div>
                        <div className="text-xs font-normal mt-0.5 text-text-muted">KB-only mode</div>
                      </button>
                    </div>

                    {searchProvider === "tavily" && (
                      <Field
                        label="Tavily API Key"
                        hint={searchSettings?.has_api_key ? "(already set — leave blank to keep)" : undefined}
                      >
                        <input
                          type="password"
                          value={searchApiKey}
                          onChange={(e) => setSearchApiKey(e.target.value)}
                          placeholder={searchSettings?.has_api_key ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" : "tvly-xxxxxxxxxxxxxxxxxx"}
                          className={inputClass}
                        />
                        <a
                          href="https://app.tavily.com/"
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-block mt-1.5 text-xs text-brand-700 hover:text-brand-hover font-inter"
                        >
                          Get a free key &rarr;
                        </a>
                      </Field>
                    )}

                    {searchProvider === "none" && (
                      <div className="p-3 rounded-lg bg-surface-subtle border border-border-ui">
                        <p className="text-xs text-text-muted font-inter">
                          Cora will only answer from the local knowledge base.
                        </p>
                      </div>
                    )}

                    {searchError && <ErrorBox message={searchError} />}

                    <SaveCancel
                      onSave={() => void handleSaveSearch()}
                      onCancel={() => onOpenChange(false)}
                      saving={searchSaving}
                    />
                  </>
                )}
              </div>
            )}

            {/* Compact config status (always visible) */}
            {configStatus && (
              <div className="border-t border-border-ui pt-4 mt-2">
                <div className="text-xs font-poppins font-semibold text-text-primary mb-2">
                  System status
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <MiniProviderCard label="LLM" status={configStatus.llm} />
                  <MiniProviderCard label="Embeddings" status={configStatus.embeddings} />
                  <MiniProviderCard label="Reranker" status={configStatus.reranker} />
                  <MiniProviderCard label="Web search" status={configStatus.search} />
                </div>
                {configStatus.warnings.length > 0 && (
                  <div className="mt-2 space-y-1">
                    {configStatus.warnings.slice(0, 3).map((w, i) => (
                      <div key={i} className="text-xs text-semantic-warning-text font-inter">
                        {"\u26A0"} {w}
                      </div>
                    ))}
                  </div>
                )}
                <p className="mt-2 text-xs text-text-muted font-inter">
                  Reranker is configured via <code>.env</code>. See the README for details.
                </p>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

function MiniProviderCard({ label, status }: { label: string; status: ProviderStatus }): JSX.Element {
  const ok = status.is_configured;
  return (
    <div className={`p-2 rounded-lg border ${ok ? "border-semantic-success-border bg-semantic-success-bg/50" : "border-semantic-warning-border bg-semantic-warning-bg/50"}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-poppins font-medium text-text-primary">{label}</span>
        <span className={`text-xs ${ok ? "text-semantic-success-text" : "text-semantic-warning-text"}`}>
          {ok ? "\u2713" : "\u26A0"}
        </span>
      </div>
      <div className="text-xs text-text-muted font-inter">
        {status.provider === "none" ? "Disabled" : status.provider}
      </div>
    </div>
  );
}

export default SettingsDialog;
