/**
 * SearchStep — configure web search provider (Tavily) or disable it.
 *
 * Web search is used when queries fall outside the knowledge base. Tavily
 * is the only supported provider. Users can disable web search entirely.
 */

import { useEffect, useState } from "react";
import {
  getSearchSettings,
  updateSearchSettings,
  type SearchSettings,
} from "@/services/llmSettingsApi";
import { StepHeading, StepActions } from "@/components/onboarding/ProviderStep";
import { Field, ErrorBox, inputClass } from "@/components/settings/settingsPrimitives";

type SearchProvider = "tavily" | "none";

interface SearchStepProps {
  onBack: () => void;
  onContinue: () => void;
}

const SearchStep = ({ onBack, onContinue }: SearchStepProps): JSX.Element => {
  const [provider, setProvider] = useState<SearchProvider>("tavily");
  const [apiKey, setApiKey] = useState("");
  const [existing, setExisting] = useState<SearchSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSearchSettings()
      .then((s) => {
        if (cancelled) return;
        setExisting(s);
        setProvider(s.provider as SearchProvider);
      })
      .catch(() => {
        /* backend down — defaults are fine */
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  const handleSave = async (): Promise<void> => {
    setError(null);
    setSaving(true);
    try {
      await updateSearchSettings({
        provider,
        api_key: apiKey || undefined,
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
        Loading search settings...
      </div>
    );
  }

  return (
    <div>
      <StepHeading
        title="Web search"
        subtitle="When a question falls outside the knowledge base, Cora can search the web for fresh information. Optional — you can disable this."
      />

      {/* Provider selection */}
      <div className="grid grid-cols-2 gap-3 mb-4">
        <button
          type="button"
          onClick={() => setProvider("tavily")}
          className={`px-4 py-3 rounded-lg border-2 text-sm font-poppins font-medium transition-all text-left ${
            provider === "tavily"
              ? "border-brand-700 bg-brand-100 text-brand-700"
              : "border-border-ui bg-surface-card text-text-secondary hover:border-brand-200"
          }`}
        >
          <div className="font-semibold">Tavily</div>
          <div className="text-xs font-normal mt-0.5 opacity-80">AI-optimized web search</div>
        </button>
        <button
          type="button"
          onClick={() => setProvider("none")}
          className={`px-4 py-3 rounded-lg border-2 text-sm font-poppins font-medium transition-all text-left ${
            provider === "none"
              ? "border-brand-700 bg-brand-100 text-brand-700"
              : "border-border-ui bg-surface-card text-text-secondary hover:border-brand-200"
          }`}
        >
          <div className="font-semibold">Disabled</div>
          <div className="text-xs font-normal mt-0.5 opacity-80">KB-only mode</div>
        </button>
      </div>

      {/* Tavily API key */}
      {provider === "tavily" && (
        <div className="mb-5">
          <label className="block text-sm font-poppins font-medium text-text-primary mb-2">
            Tavily API Key
            {existing?.has_api_key && (
              <span className="ml-2 text-xs text-semantic-success-icon font-normal">
                (already set — leave blank to keep)
              </span>
            )}
          </label>
          <input
            type="password"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            placeholder={existing?.has_api_key ? "\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022\u2022" : "tvly-xxxxxxxxxxxxxxxxxx"}
            className={inputClass}
          />
          <a
            href="https://app.tavily.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block mt-1.5 text-xs text-brand-700 hover:text-brand-hover font-inter"
          >
            Get a free Tavily key &rarr;
          </a>
          <p className="mt-1.5 text-xs text-text-muted font-inter">
            Free tier: 1,000 searches/month. No credit card required.
          </p>
        </div>
      )}

      {/* Disabled info */}
      {provider === "none" && (
        <div className="mb-5 p-3 rounded-lg bg-surface-subtle border border-border-ui">
          <p className="text-xs text-text-muted font-inter">
            Cora will only answer from the local knowledge base. Questions outside the KB will
            return "Information not found." You can enable web search later in Settings.
          </p>
        </div>
      )}

      {error && <div className="mb-5"><ErrorBox message={error} /></div>}

      <StepActions
        onBack={onBack}
        onContinue={() => void handleSave()}
        continueLabel={provider === "none" ? "Continue" : "Save & continue"}
        saving={saving}
      />
    </div>
  );
};

export default SearchStep;
