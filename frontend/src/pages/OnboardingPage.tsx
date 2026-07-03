/**
 * OnboardingPage — guided multi-step setup wizard with auto-detection.
 *
 * On load, checks the backend for existing config (from .env or DB).
 * If a provider is already configured (e.g. GEMINI_API_KEY in .env),
 * that step is automatically skipped with a "We detected your config"
 * message on the welcome screen.
 *
 * Dynamic step list — only unconfigured providers are shown:
 *   - Welcome        (always shown, with detection summary)
 *   - Provider       (skipped if LLM is configured)
 *   - Credentials    (skipped if LLM is configured)
 *   - Embeddings     (skipped if embeddings are configured)
 *   - Search         (skipped if search is configured or disabled)
 *   - Review         (always shown — confirms the full config)
 *   - Tour           (always shown — feature showcase + finish)
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { ServerOff } from "lucide-react";
import { checkHealth } from "@/services/coraApi";
import {
  getLLMSettings,
  getEmbeddingSettings,
  getSearchSettings,
  type LLMSettings,
  type EmbeddingSettings,
  type SearchSettings,
} from "@/services/llmSettingsApi";
import {
  PRESETS,
  presetFromSettings,
  type LlmFormState,
  type ProviderPreset,
} from "@/components/onboarding/llmPresets";
import { markOnboardingComplete } from "@/components/onboarding/onboardingState";
import WelcomeStep from "@/components/onboarding/WelcomeStep";
import ProviderStep from "@/components/onboarding/ProviderStep";
import CredentialsStep from "@/components/onboarding/CredentialsStep";
import EmbeddingsStep from "@/components/onboarding/EmbeddingsStep";
import SearchStep from "@/components/onboarding/SearchStep";
import StatusStep from "@/components/onboarding/StatusStep";
import TourStep from "@/components/onboarding/TourStep";

type StepId = "welcome" | "provider" | "credentials" | "embeddings" | "search" | "review" | "tour";

interface DetectionResult {
  llm: LLMSettings | null;
  embeddings: EmbeddingSettings | null;
  search: SearchSettings | null;
}

const OnboardingPage = (): JSX.Element => {
  const navigate = useNavigate();
  const [stepIndex, setStepIndex] = useState(0);
  const [detection, setDetection] = useState<DetectionResult>({
    llm: null,
    embeddings: null,
    search: null,
  });
  const [loading, setLoading] = useState(true);
  const [backendDown, setBackendDown] = useState(false);
  const shouldReduceMotion = useReducedMotion();

  // Shared form state across provider + credentials steps
  const [form, setForm] = useState<LlmFormState>({
    preset: "gemini",
    apiKey: "",
    baseUrl: "",
    modelMain: "",
  });

  const patchForm = useCallback((patch: Partial<LlmFormState>) => {
    setForm((prev) => ({ ...prev, ...patch }));
  }, []);

  // Check backend health first, then load provider settings only if reachable.
  useEffect(() => {
    let cancelled = false;
    checkHealth()
      .then((health) => {
        if (cancelled) return;
        if (!health.healthy) {
          setBackendDown(true);
          return;
        }
        return Promise.all([
          getLLMSettings().catch(() => null),
          getEmbeddingSettings().catch(() => null),
          getSearchSettings().catch(() => null),
        ]).then(([llm, emb, search]) => {
          if (cancelled) return;
          setDetection({ llm, embeddings: emb, search });
          if (llm) {
            const detected = presetFromSettings(llm);
            setForm((prev) => ({
              ...prev,
              preset: detected,
              baseUrl: llm.base_url ?? PRESETS[detected].base_url ?? "",
              modelMain: llm.model_main ?? "",
            }));
          }
        });
      })
      .catch(() => {
        if (!cancelled) setBackendDown(true);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  // When preset changes, update base_url to the preset default
  useEffect(() => {
    setForm((prev) => {
      const config = PRESETS[prev.preset];
      if (config.base_url !== null) {
        return { ...prev, baseUrl: config.base_url };
      }
      return prev;
    });
  }, [form.preset]);

  // Build the dynamic step list based on what's already configured
  const steps = useMemo<StepId[]>(() => {
    const result: StepId[] = ["welcome"];
    const llmConfigured = detection.llm?.is_configured ?? false;
    const embConfigured = detection.embeddings?.is_configured ?? false;
    const searchConfigured = detection.search?.is_configured ?? false;

    if (!llmConfigured) {
      result.push("provider", "credentials");
    }
    if (!embConfigured) {
      result.push("embeddings");
    }
    if (!searchConfigured) {
      result.push("search");
    }
    result.push("review", "tour");
    return result;
  }, [detection]);

  const currentStep = steps[stepIndex] ?? "welcome";

  const goToStep = useCallback((id: StepId) => {
    setStepIndex(steps.indexOf(id));
  }, [steps]);

  const nextStep = useCallback(() => {
    setStepIndex((prev) => Math.min(prev + 1, steps.length - 1));
  }, [steps.length]);

  const prevStep = useCallback(() => {
    setStepIndex((prev) => Math.max(prev - 1, 0));
  }, []);

  const finish = useCallback(() => {
    markOnboardingComplete();
    navigate("/");
  }, [navigate]);

  const skip = useCallback(() => {
    markOnboardingComplete();
    navigate("/");
  }, [navigate]);

  if (loading) {
    return (
      <div className="min-h-screen bg-surface-base flex items-center justify-center">
        <div className="animate-pulse text-text-muted font-inter text-sm">Loading...</div>
      </div>
    );
  }

  // If the backend is down, we can't detect existing config. Show a clear
  // message instead of asking for all API keys (which the user may already
  // have in their .env file).
  if (backendDown) {
    return (
      <div className="min-h-screen bg-surface-base flex flex-col items-center justify-center px-6 py-10">
        <div className="w-full max-w-md text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-surface-subtle border border-border-ui mb-4">
            <ServerOff className="h-5 w-5 text-text-muted" strokeWidth={1.75} />
          </div>
          <h1 className="font-poppins text-xl font-semibold text-text-primary mb-2">
            Backend not reachable
          </h1>
          <p className="font-inter text-sm text-text-muted mb-6">
            Cora&apos;s backend server isn&apos;t running. If you&apos;ve already configured your API keys
            in the backend <code className="px-1 py-0.5 rounded bg-surface-subtle text-text-primary">.env</code>{" "}
            file, start the backend and refresh — onboarding will skip the steps you&apos;ve already set up.
          </p>
          <div className="flex flex-col items-center gap-3">
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="px-6 py-2.5 rounded-lg bg-brand-700 text-white font-poppins text-sm font-semibold shadow-card-md transition-colors hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500"
            >
              Retry connection
            </button>
            <button
              type="button"
              onClick={skip}
              className="font-inter text-sm text-text-muted hover:text-text-primary transition-colors"
            >
              Skip to chat anyway
            </button>
          </div>
          <div className="mt-6 p-3 rounded-xl bg-surface-card border border-border-ui text-left">
            <p className="font-inter text-xs text-text-muted">
              <span className="font-medium text-text-primary">To start the backend:</span>{" "}
              <code className="text-text-primary">python -m src.api.main</code>
            </p>
          </div>
        </div>
      </div>
    );
  }

  // Detection summary for the welcome step
  const detectedItems: { label: string; detail: string }[] = [];
  if (detection.llm?.is_configured) {
    const preset = presetFromSettings(detection.llm);
    detectedItems.push({
      label: "AI Model",
      detail: `${PRESETS[preset].label} — ${detection.llm.model_main ?? "configured"}`,
    });
  }
  if (detection.embeddings?.is_configured) {
    detectedItems.push({
      label: "Embeddings",
      detail: `${detection.embeddings.provider} — ${detection.embeddings.model}`,
    });
  }
  if (detection.search?.is_configured) {
    if (detection.search.provider === "none") {
      detectedItems.push({ label: "Web Search", detail: "Disabled (KB-only mode)" });
    } else {
      detectedItems.push({ label: "Web Search", detail: detection.search.provider });
    }
  }

  const allConfigured = detectedItems.length === 3;
  const isLlmConfigured = detection.llm?.is_configured ?? false;

  return (
    <div className="min-h-screen bg-surface-base flex flex-col items-center justify-center px-6 py-6 md:py-8">
      <div className="w-full max-w-2xl">
        {/* Skip link (top-right) — hidden on the final tour step */}
        {currentStep !== "tour" && (
          <div className="flex justify-end mb-3">
            <button
              type="button"
              onClick={skip}
              className="font-inter text-xs text-text-muted hover:text-text-primary transition-colors"
            >
              Skip setup &rarr;
            </button>
          </div>
        )}

        {/* Progress indicator */}
        <StepProgress current={stepIndex} labels={steps} />

        {/* Step content with transition */}
        <div className="mt-6 min-h-[360px]">
          <AnimatePresence mode="wait">
            <motion.div
              key={currentStep}
              initial={shouldReduceMotion ? { opacity: 1 } : { opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={shouldReduceMotion ? { opacity: 1 } : { opacity: 0 }}
              transition={{ duration: shouldReduceMotion ? 0 : 0.2, ease: [0.4, 0, 0.2, 1] }}
            >
              {currentStep === "welcome" && (
                <WelcomeStep
                  isConfigured={isLlmConfigured}
                  onContinue={nextStep}
                  onSkip={skip}
                  detectedItems={detectedItems}
                  allConfigured={allConfigured}
                />
              )}

              {currentStep === "provider" && (
                <ProviderStep
                  preset={form.preset}
                  onChange={(preset: ProviderPreset) => patchForm({ preset })}
                  onBack={prevStep}
                  onContinue={nextStep}
                />
              )}

              {currentStep === "credentials" && (
                <CredentialsStep
                  form={form}
                  settings={detection.llm}
                  onFormChange={patchForm}
                  onBack={prevStep}
                  onSaved={nextStep}
                />
              )}

              {currentStep === "embeddings" && (
                <EmbeddingsStep
                  onBack={prevStep}
                  onContinue={nextStep}
                />
              )}

              {currentStep === "search" && (
                <SearchStep
                  onBack={prevStep}
                  onContinue={nextStep}
                />
              )}

              {currentStep === "review" && (
                <StatusStep onBack={prevStep} onContinue={nextStep} />
              )}

              {currentStep === "tour" && <TourStep onFinish={finish} />}
            </motion.div>
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};

/** Horizontal stepper with text labels so users know where they are. */
function StepProgress({
  current,
  labels,
}: {
  current: number;
  labels: readonly StepId[];
}): JSX.Element {
  const LABEL_MAP: Record<StepId, string> = {
    welcome: "Welcome",
    provider: "Provider",
    credentials: "Credentials",
    embeddings: "Embeddings",
    search: "Search",
    review: "Review",
    tour: "Tour",
  };

  return (
    <div className="flex items-center justify-center gap-2" aria-label="Onboarding progress">
      {labels.map((stepId, i) => {
        const state = i < current ? "done" : i === current ? "current" : "upcoming";
        const label = LABEL_MAP[stepId];
        return (
          <div key={stepId} className="flex items-center gap-2">
            <span
              className={`font-inter text-xs transition-colors ${
                state === "current"
                  ? "text-text-primary font-semibold"
                  : state === "done"
                  ? "text-brand-700"
                  : "text-text-muted"
              }`}
            >
              {label}
            </span>
            {i < labels.length - 1 && (
              <span
                className={`w-4 h-px ${state === "done" ? "bg-brand-700" : "bg-border-ui"}`}
                aria-hidden="true"
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default OnboardingPage;
