/**
 * CredentialsStep — collect API key, base URL, and model for the chosen
 * provider, test the connection, then save via the shared saveLlmForm helper.
 */

import { useEffect, useState } from "react";
import {
  listLLMModels,
  testLLMConnection,
  type LLMModel,
  type LLMSettings,
  type LLMTestResult,
} from "@/services/llmSettingsApi";
import { PRESETS, saveLlmForm, type LlmFormState } from "@/components/onboarding/llmPresets";
import { StepHeading, StepActions } from "@/components/onboarding/ProviderStep";
import {
  Field,
  TestConnection,
  ErrorBox,
  inputClass,
  type TestState,
} from "@/components/settings/settingsPrimitives";

interface CredentialsStepProps {
  form: LlmFormState;
  settings: LLMSettings | null;
  onFormChange: (patch: Partial<LlmFormState>) => void;
  onBack: () => void;
  onSaved: () => void;
}

const CredentialsStep = ({
  form,
  settings,
  onFormChange,
  onBack,
  onSaved,
}: CredentialsStepProps): JSX.Element => {
  const config = PRESETS[form.preset];
  const [ollamaModels, setOllamaModels] = useState<LLMModel[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [testState, setTestState] = useState<TestState>("idle");
  const [testResult, setTestResult] = useState<LLMTestResult | null>(null);

  // Fetch Ollama models when the preset is ollama
  useEffect(() => {
    if (form.preset !== "ollama") {
      setOllamaModels([]);
      return;
    }
    const url = form.baseUrl || "http://localhost:11434/v1";
    setLoadingModels(true);
    listLLMModels(url.replace("/v1", ""))
      .then(setOllamaModels)
      .catch(() => setOllamaModels([]))
      .finally(() => setLoadingModels(false));
  }, [form.preset, form.baseUrl]);

  // Reset test state when any form field changes (stale test result)
  useEffect(() => {
    setTestState("idle");
    setTestResult(null);
  }, [form.apiKey, form.baseUrl, form.modelMain, form.preset]);

  const handleTest = async (): Promise<void> => {
    setError(null);
    setTestState("testing");
    setTestResult(null);

    if (config.needsApiKey && !form.apiKey && !settings?.has_api_key) {
      setTestState("failed");
      setTestResult({ success: false, message: "API key is required." });
      return;
    }
    if (config.provider === "openai_compatible" && !form.baseUrl) {
      setTestState("failed");
      setTestResult({ success: false, message: "Base URL is required." });
      return;
    }
    if (!form.modelMain) {
      setTestState("failed");
      setTestResult({ success: false, message: "Model name is required." });
      return;
    }

    try {
      const result = await testLLMConnection({
        provider: config.provider,
        api_key: form.apiKey || undefined,
        base_url: config.provider === "gemini" ? undefined : form.baseUrl,
        model_main: form.modelMain,
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

  const handleSave = async (): Promise<void> => {
    setError(null);
    setSaving(true);
    try {
      await saveLlmForm(form, settings);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <StepHeading
        title={`Configure ${config.label}`}
        subtitle="Enter the details for your chosen provider. Test the connection before saving to catch typos early."
      />

      {/* API Key */}
      {config.needsApiKey && (
        <Field label="API Key" className="mb-5" hint={settings?.has_api_key ? "(already set — leave blank to keep existing)" : undefined}>
          <input
            type="password"
            value={form.apiKey}
            onChange={(e) => onFormChange({ apiKey: e.target.value })}
            placeholder={settings?.has_api_key ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" : "Enter your API key"}
            className={inputClass}
          />
        </Field>
      )}

      {/* Base URL */}
      {config.needsBaseUrl && (
        <Field label="Base URL" className="mb-5">
          <input
            type="text"
            value={form.baseUrl}
            onChange={(e) => onFormChange({ baseUrl: e.target.value })}
            placeholder="https://api.example.com/v1"
            className={inputClass}
          />
        </Field>
      )}

      {/* Model */}
      <Field label="Model" className="mb-5">
        {form.preset === "ollama" && ollamaModels.length > 0 ? (
          <select
            value={form.modelMain}
            onChange={(e) => onFormChange({ modelMain: e.target.value })}
            className={inputClass}
          >
            <option value="">Select a model...</option>
            {ollamaModels.map((m) => (
              <option key={m.name} value={m.name}>
                {m.name}
                {m.parameter_size ? ` (${m.parameter_size})` : ""}
                {m.family ? ` \u2014 ${m.family}` : ""}
              </option>
            ))}
          </select>
        ) : form.preset === "ollama" && loadingModels ? (
          <div className="text-sm text-text-muted font-inter">Loading available models...</div>
        ) : (
          <input
            type="text"
            value={form.modelMain}
            onChange={(e) => onFormChange({ modelMain: e.target.value })}
            placeholder={config.modelPlaceholder}
            className={inputClass}
          />
        )}
        {form.preset === "ollama" && ollamaModels.length === 0 && !loadingModels && (
          <p className="mt-2 text-xs text-semantic-warning-icon font-inter">
            No models found. Make sure Ollama is running (<code>ollama serve</code>) and you&apos;ve
            pulled a model (<code>ollama pull &lt;model-name&gt;</code>). You can also enter the
            model name manually above.
          </p>
        )}
      </Field>

      {/* Test connection */}
      <div className="mb-5">
        <TestConnection
          state={testState}
          result={testResult}
          onTest={() => void handleTest()}
        />
      </div>

      {error && <div className="mb-5"><ErrorBox message={error} /></div>}

      <p className="mb-6 text-xs text-text-muted font-inter">
        Note: after changing the provider, the backend needs to restart for the new client to take
        effect.
      </p>

      <StepActions
        onBack={onBack}
        onContinue={() => void handleSave()}
        continueLabel="Save & continue"
        saving={saving}
      />
    </div>
  );
};

export default CredentialsStep;
