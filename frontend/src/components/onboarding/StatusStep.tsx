/**
 * StatusStep — review full configuration status after saving LLM settings.
 *
 * Pulls /v1/settings/status and shows each provider's readiness plus any
 * validation warnings (e.g. embedding dimension mismatch). Embeddings,
 * reranker, and web search are configured via .env, so this step surfaces a
 * hint pointing the user there for anything still incomplete.
 */

import { useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { CheckCircle2, AlertCircle } from "lucide-react";
import {
  getConfigStatus,
  type ConfigStatus,
  type ProviderStatus,
} from "@/services/llmSettingsApi";
import { StepHeading, StepActions } from "@/components/onboarding/ProviderStep";

interface StatusStepProps {
  onBack: () => void;
  onContinue: () => void;
}

const StatusStep = ({ onBack, onContinue }: StatusStepProps): JSX.Element => {
  const [status, setStatus] = useState<ConfigStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const shouldReduceMotion = useReducedMotion();

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getConfigStatus()
      .then((s) => {
        if (!cancelled) setStatus(s);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div>
        <StepHeading title="Review your setup" subtitle="Checking all providers..." />
        <div className="animate-pulse">
          <div className="h-11 rounded-lg bg-surface-subtle mb-5" />
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
            <div className="h-16 rounded-lg bg-surface-subtle" />
            <div className="h-16 rounded-lg bg-surface-subtle" />
            <div className="h-16 rounded-lg bg-surface-subtle" />
            <div className="h-16 rounded-lg bg-surface-subtle" />
          </div>
          <div className="h-16 rounded-lg bg-surface-subtle mb-5" />
        </div>
      </div>
    );
  }

  if (error || !status) {
    return (
      <div>
        <StepHeading title="Review your setup" subtitle="Could not load configuration status." />
        <div className="mb-6 p-3.5 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-sm">
          {error ?? "Unknown error"}
        </div>
        <StepActions onBack={onBack} onContinue={onContinue} continueLabel="Continue anyway" />
      </div>
    );
  }

  const providers: Array<{ label: string; status: ProviderStatus; envHint?: string }> = [
    { label: "LLM", status: status.llm },
    { label: "Embeddings", status: status.embeddings, envHint: "Set EMBEDDING_PROVIDER and the matching API key in .env" },
    { label: "Reranker", status: status.reranker, envHint: "Set RERANK_PROVIDER (voyage, cohere, or none) in .env" },
    { label: "Web search", status: status.search, envHint: "Set SEARCH_PROVIDER (tavily or none) in .env" },
  ];

  return (
    <div>
      <StepHeading
        title="Review your setup"
        subtitle="Here's how every part of Cora is configured. Items in .env-only settings can be updated later."
      />

      {/* Overall readiness banner */}
      <motion.div
        className={`flex items-center gap-2.5 p-3.5 rounded-lg mb-5 text-sm font-inter border ${
          status.ready
            ? "bg-surface-card border-border-ui text-text-primary"
            : "bg-surface-card border-border-ui text-text-primary"
        }`}
        initial={shouldReduceMotion ? { opacity: 1, y: 0 } : { opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: shouldReduceMotion ? 0 : 0.3 }}
      >
        {status.ready ? (
          <>
            <CheckCircle2 className="w-4 h-4 text-semantic-success-text flex-shrink-0" strokeWidth={2} />
            <span>All providers configured. Cora is ready to go.</span>
          </>
        ) : (
          <>
            <AlertCircle className="w-4 h-4 text-semantic-warning-text flex-shrink-0" strokeWidth={2} />
            <span>Some providers aren't configured yet — you can still continue and finish setup in .env.</span>
          </>
        )}
      </motion.div>

      {/* Provider status grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-5">
        {providers.map(({ label, status: ps, envHint }) => (
          <ProviderCard key={label} label={label} status={ps} envHint={envHint} />
        ))}
      </div>

      {/* Qdrant info */}
      {status.qdrant && (
        <div className="p-3.5 rounded-lg bg-surface-card border border-border-ui mb-5">
          <div className="text-sm font-poppins font-medium text-text-primary mb-1">Qdrant</div>
          {status.qdrant.error ? (
            <div className="text-xs text-semantic-error-icon font-inter">
              Connection error: {status.qdrant.error}
            </div>
          ) : (
            <div className="text-xs text-text-muted font-inter">
              Collection: {status.qdrant.collection} &middot; Vectors: {status.qdrant.vector_dim}d
              &middot; Points: {status.qdrant.points_count?.toLocaleString() ?? "unknown"}
            </div>
          )}
        </div>
      )}

      {/* Warnings */}
      {status.warnings.length > 0 && (
        <div className="space-y-2 mb-6">
          {status.warnings.map((w, i) => (
            <div
              key={i}
              className="p-3 rounded-lg bg-semantic-warning-bg border border-semantic-warning-border text-semantic-warning-text font-inter text-xs"
            >
              {w}
            </div>
          ))}
        </div>
      )}

      <StepActions onBack={onBack} onContinue={onContinue} continueLabel="Continue" />
    </div>
  );
};

function ProviderCard({
  label,
  status,
  envHint,
}: {
  label: string;
  status: ProviderStatus;
  envHint?: string;
}): JSX.Element {
  const ok = status.is_configured;
  return (
    <div className="p-3.5 rounded-lg border border-border-ui bg-surface-card">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-poppins font-medium text-text-primary">{label}</span>
        <span
          className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-inter font-medium ${
            ok
              ? "bg-semantic-success-bg text-semantic-success-text"
              : "bg-semantic-warning-bg text-semantic-warning-text"
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${ok ? "bg-semantic-success-icon" : "bg-semantic-warning-icon"}`} />
          {ok ? "Ready" : "Incomplete"}
        </span>
      </div>
      <div className="text-xs text-text-muted font-inter">
        {status.provider === "none" ? "Disabled" : status.provider}
        {status.model && status.provider !== "none" ? ` \u00B7 ${status.model}` : ""}
      </div>
      {status.warning && (
        <div className="mt-1.5 text-xs text-semantic-warning-text font-inter">{status.warning}</div>
      )}
      {!ok && envHint && !status.warning && (
        <div className="mt-1.5 text-xs text-text-muted font-inter">{envHint}</div>
      )}
    </div>
  );
}

export default StatusStep;
