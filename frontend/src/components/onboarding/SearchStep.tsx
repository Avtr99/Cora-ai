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
import {
  SEARCH_PROVIDER_PRESETS,
  type SearchProvider,
} from "@/components/onboarding/searchPresets";
import { Field, ErrorBox, ProviderGrid, inputClass } from "@/components/settings/settingsPrimitives";

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
      <div className="py-8 3xl:py-10 4xl:py-12 text-center text-text-muted font-inter text-body-sm 3xl:text-base 4xl:text-lg animate-pulse">
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
      <div className="mb-4 3xl:mb-5 4xl:mb-6">
        <ProviderGrid
          presets={SEARCH_PROVIDER_PRESETS}
          selected={provider}
          onSelect={setProvider}
          columns={2}
          size="roomy"
          descriptions
        />
      </div>

      {/* Tavily API key */}
      {provider === "tavily" && (
        <div className="mb-5 3xl:mb-6 4xl:mb-7">
          <Field
            label="Tavily API Key"
            hint={existing?.has_api_key ? "(already set — leave blank to keep)" : undefined}
          >
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
              className="inline-block mt-1.5 3xl:mt-2 text-caption 3xl:text-sm 4xl:text-base text-brand-700 hover:text-brand-hover font-inter rounded-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
            >
              Get a free Tavily key &rarr;
            </a>
            <p className="mt-1.5 3xl:mt-2 text-caption 3xl:text-sm 4xl:text-base text-text-muted font-inter">
              Free tier: 1,000 searches/month. No credit card required.
            </p>
          </Field>
        </div>
      )}

      {/* Disabled info */}
      {provider === "none" && (
        <div className="mb-5 3xl:mb-6 4xl:mb-7 p-3 3xl:p-4 4xl:p-5 rounded-lg bg-surface-subtle border border-border-ui">
          <p className="text-caption 3xl:text-sm 4xl:text-base text-text-muted font-inter">
            Cora will only answer from the local knowledge base. Questions outside the KB will
            return "Information not found." You can enable web search later in Settings.
          </p>
        </div>
      )}

      {error && <div className="mb-5 3xl:mb-6 4xl:mb-7"><ErrorBox message={error} /></div>}

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
