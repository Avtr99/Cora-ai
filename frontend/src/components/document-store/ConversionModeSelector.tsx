import React from 'react';
import { AlertCircle } from 'lucide-react';
import {
  CONVERSION_OPTIONS,
  type ConversionMode,
  type ConversionCapabilities,
  type ConversionModeInfo,
} from '@/services/documentStoreApi';

const SPEED_LABELS: Record<string, string> = {
  fast: 'Fast',
  medium: 'Medium',
  slow: 'Slow (~2 min/page)',
  very_slow: 'Very slow (10+ min/page)',
};

interface ConversionModeSelectorProps {
  conversionMode: ConversionMode;
  setConversionMode: (mode: ConversionMode) => void;
  capabilities: ConversionCapabilities | null;
}

export const ConversionModeSelector: React.FC<ConversionModeSelectorProps> = ({
  conversionMode,
  setConversionMode,
  capabilities,
}) => {
  return (
    <div role="radiogroup" aria-label="PDF parse mode" className="overflow-hidden rounded-lg border border-border-ui divide-y divide-border-ui bg-surface-card">
      {CONVERSION_OPTIONS.map((option) => {
        const modeInfo: ConversionModeInfo | undefined = capabilities?.[option.value];
        const available = modeInfo?.available ?? (option.value === 'standard');
        const selected = conversionMode === option.value;
        const isExperimental = modeInfo?.experimental ?? false;

        // Provider / model badge (only for LLM API; the standard option is local
        // and the model name is repetitive with its description).
        let badge: string | null = null;
        if (available && option.value === 'llm_api' && modeInfo?.model && modeInfo.provider) {
          const providerLabel = modeInfo.provider === 'gemini' ? 'Gemini' : 'OpenAI';
          badge = `${providerLabel} · ${modeInfo.model}`;
        }

        // Hint: why it's unavailable
        let hint: string | null = null;
        if (!available) {
          if (option.value === 'llm_api') {
            hint = 'Configure Gemini or OpenAI API key in Settings to enable.';
          } else if (option.value === 'standard') {
            hint = 'Docling dependencies are not installed on the server. Reinstall with `pip install -r requirements.txt`.';
          }
        }

        // Warning: paid API key required for llm_api (one API call per page)
        let rateLimitWarning: string | null = null;
        if (available && option.value === 'llm_api') {
          rateLimitWarning = 'Paid API key required. One request is sent per PDF page.';
        }

        // Prefer the server's values, but fall back to each mode's static facts
        // so we never render a meaningless "—". The server only sends a usable
        // cost when the mode is configured; otherwise use the known estimate.
        const serverCost = modeInfo?.cost_per_page;
        const costLabel = serverCost && serverCost !== '—' ? serverCost : option.defaults.cost;
        const speedKey = modeInfo?.speed ?? option.defaults.speed;
        const speedLabel = SPEED_LABELS[speedKey] ?? speedKey;
        const isExternal = (modeInfo?.privacy ?? option.defaults.privacy) === 'external';
        const isFreeCost = costLabel.toLowerCase() === 'free';

        return (
          <label
            key={option.value}
            className={`flex cursor-pointer gap-3 px-3.5 py-3 transition-colors ${
              selected
                ? 'bg-brand-50'
                : available
                  ? 'bg-surface-card hover:bg-surface-subtle/60'
                  : 'bg-surface-subtle/30 cursor-not-allowed'
            }`}
          >
            <input
              type="radio"
              name="pdf-conversion-mode"
              value={option.value}
              checked={selected}
              disabled={!available}
              onChange={() => available && setConversionMode(option.value)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-brand-700 disabled:cursor-not-allowed"
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`font-poppins text-sm font-semibold ${selected ? 'text-text-primary' : available ? 'text-text-primary' : 'text-text-muted'}`}>
                    {option.label}
                  </span>
                  {isExperimental && (
                    <span className="inline-flex items-center rounded px-1.5 py-0.5 font-inter text-2xs font-semibold uppercase tracking-wide bg-semantic-warning-bg text-semantic-warning-text border border-semantic-warning-border">
                      Advanced
                    </span>
                  )}
                  {!available && (
                    <span className="inline-flex items-center rounded px-1.5 py-0.5 font-inter text-2xs font-semibold uppercase tracking-wide bg-surface-card text-text-muted border border-border-ui">
                      Unavailable
                    </span>
                  )}
                </div>
                {badge && available && (
                  <span className={`inline-flex shrink-0 rounded-md px-2 py-0.5 font-inter text-xs font-medium border ${selected ? 'bg-surface-card text-brand-700 border-brand-200' : 'bg-surface-subtle text-text-secondary border-border-ui'}`}>
                    {badge}
                  </span>
                )}
              </div>
              <p className={`mt-1 font-inter text-xs leading-relaxed ${selected ? 'text-text-secondary' : available ? 'text-text-secondary' : 'text-text-muted'}`}>
                {option.description}
              </p>
              <div className="mt-2.5 flex flex-wrap items-center gap-x-3 gap-y-1 font-inter text-xs">
                <span className="text-text-muted">
                  Cost:{' '}
                  <span className={`font-semibold ${isFreeCost ? 'text-semantic-success-text' : available ? 'text-text-primary' : 'text-text-secondary'}`}>
                    {costLabel}
                  </span>
                </span>
                <span className="text-border-ui" aria-hidden="true">·</span>
                <span className="text-text-muted">
                  Speed: <span className={`font-semibold ${available ? 'text-text-primary' : 'text-text-muted'}`}>{speedLabel}</span>
                </span>
                <span className="text-border-ui" aria-hidden="true">·</span>
                <span className="text-text-muted">
                  Privacy:{' '}
                  <span className={`font-semibold ${isExternal ? 'text-semantic-warning-text' : 'text-semantic-success-text'}`}>
                    {isExternal ? 'External API' : 'Local only'}
                  </span>
                </span>
              </div>
              {hint && (
                <p className="mt-2 font-inter text-xs text-text-muted">
                  {hint}
                </p>
              )}
              {rateLimitWarning && (
                <div className="mt-2 flex items-start gap-1.5 rounded-md bg-semantic-warning-bg/50 border border-semantic-warning-border px-2 py-1.5 font-inter text-xs text-semantic-warning-text">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-semantic-warning-text" aria-hidden="true" />
                  <span>{rateLimitWarning}</span>
                </div>
              )}
            </div>
          </label>
        );
      })}
    </div>
  );
};
