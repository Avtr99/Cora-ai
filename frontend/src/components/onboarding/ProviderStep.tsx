/**
 * ProviderStep — choose the LLM provider preset.
 *
 * Pure selection step; credentials are collected on the next step so the
 * user isn't overwhelmed with fields before they've picked a provider.
 */

import { motion } from "framer-motion";
import { PRESETS, type ProviderPreset } from "@/components/onboarding/llmPresets";
import { ProviderGrid } from "@/components/settings/settingsPrimitives";

interface ProviderStepProps {
  preset: ProviderPreset;
  onChange: (preset: ProviderPreset) => void;
  onBack: () => void;
  onContinue: () => void;
}

const ProviderStep = ({ preset, onChange, onBack, onContinue }: ProviderStepProps): JSX.Element => {
  const config = PRESETS[preset];

  return (
    <div>
      <StepHeading
        title="Choose your AI provider"
        subtitle="Pick the service that will power Cora's answers. You can change this anytime in Settings."
      />

      <div className="mb-4 3xl:mb-5 4xl:mb-6">
        <ProviderGrid presets={PRESETS} selected={preset} onSelect={onChange} size="roomy" />
      </div>

      <motion.p
        key={preset}
        className="text-caption 3xl:text-sm 4xl:text-base text-text-muted font-inter mb-8 3xl:mb-10 4xl:mb-12"
        initial={{ opacity: 0, y: 4 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.25 }}
      >
        {config.description}
      </motion.p>

      <StepActions onBack={onBack} onContinue={onContinue} continueLabel="Continue" />
    </div>
  );
};

// ---------------------------------------------------------------------------
// Shared step primitives (kept here to avoid a separate file; small + focused)
// ---------------------------------------------------------------------------

export function StepHeading({ title, subtitle }: { title: string; subtitle: string }): JSX.Element {
  return (
    <div className="mb-6 3xl:mb-8 4xl:mb-10">
      <h2 className="font-poppins text-heading-1 3xl:text-display font-semibold text-text-primary mb-1.5 3xl:mb-2 4xl:mb-3">
        {title}
      </h2>
      <p className="font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-muted">{subtitle}</p>
    </div>
  );
}

export function StepActions({
  onBack,
  onContinue,
  continueLabel,
  continueDisabled,
  saving,
}: {
  onBack: () => void;
  onContinue: () => void;
  continueLabel: string;
  continueDisabled?: boolean;
  saving?: boolean;
}): JSX.Element {
  return (
    <div className="flex items-center gap-3 3xl:gap-4 4xl:gap-5">
      <button
        type="button"
        onClick={onBack}
        className="px-5 3xl:px-6 py-2.5 3xl:py-3 4xl:py-4 rounded-lg border border-border-ui text-text-secondary font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-medium transition-colors hover:border-text-muted hover:bg-surface-subtle focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2"
      >
        Back
      </button>
      <button
        type="button"
        onClick={onContinue}
        disabled={continueDisabled || saving}
        className="px-6 3xl:px-8 py-2.5 3xl:py-3 4xl:py-4 rounded-lg bg-brand-700 text-white font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-semibold shadow-card-md transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-focus"
      >
        {saving ? "Saving..." : continueLabel}
      </button>
    </div>
  );
}

export default ProviderStep;
