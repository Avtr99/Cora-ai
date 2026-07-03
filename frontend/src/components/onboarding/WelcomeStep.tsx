/**
 */

import { motion, useReducedMotion } from "framer-motion";
import { CheckCircle2 } from "lucide-react";

/**
 * WelcomeStep — first onboarding step.
 *
 * Introduces Cora, surfaces any existing provider config detected from the
 * backend, and offers a primary CTA plus a secondary action. Kept compact so
 * the entire onboarding viewport fits without vertical scrolling on typical
 * laptop screens.
 */

interface DetectedItem {
  label: string;
  detail: string;
}

interface WelcomeStepProps {
  isConfigured: boolean;
  onContinue: () => void;
  onSkip: () => void;
  /** Providers detected from existing .env or DB config. */
  detectedItems?: DetectedItem[];
  /** True if all three providers (LLM, embeddings, search) are configured. */
  allConfigured?: boolean;
}

const WelcomeStep = ({
  isConfigured,
  onContinue,
  onSkip,
  detectedItems = [],
  allConfigured = false,
}: WelcomeStepProps): JSX.Element => {
  const shouldReduceMotion = useReducedMotion();
  return (
    <div className="flex flex-col items-center text-center">
      <motion.img
        src="/cora.svg"
        alt=""
        aria-hidden="true"
        className="w-14 h-14 mb-5"
        initial={shouldReduceMotion ? false : { opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1] }}
      />

      <motion.h1
        className="font-poppins text-3xl leading-8 md:text-4xl md:leading-10 font-semibold text-text-primary tracking-tight mb-2"
        initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1], delay: 0.06 }}
      >
        Welcome to Cora
      </motion.h1>

      <motion.p
        className="font-inter text-sm text-text-muted max-w-sm mb-8"
        initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.4, 0, 0.2, 1], delay: 0.12 }}
      >
        Your AI assistant for the Voluntary Carbon Market, backed by the documents you trust.
      </motion.p>

      {/* Detection summary — shown only when existing config was found */}
      {detectedItems.length > 0 && (
        <motion.div
          className="w-full max-w-sm mb-8"
          initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1], delay: 0.18 }}
        >
          <div className="flex items-center justify-center gap-2 mb-3">
            <div className="flex h-5 w-5 items-center justify-center rounded-full bg-semantic-success-bg">
              <CheckCircle2 className="h-3.5 w-3.5 text-semantic-success-icon" strokeWidth={2.5} />
            </div>
            <span className="font-poppins text-sm font-semibold text-text-primary">
              {allConfigured ? "Your setup is ready" : "Existing config detected"}
            </span>
          </div>
          <div className="rounded-xl border border-border-ui bg-surface-card p-3 text-left">
            <div className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-xs">
              {detectedItems.map((item) => (
                <>
                  <span key={`${item.label}-label`} className="font-poppins font-medium text-text-secondary">
                    {item.label}
                  </span>
                  <span key={`${item.label}-detail`} className="font-inter text-text-muted truncate">
                    {item.detail}
                  </span>
                </>
              ))}
            </div>
          </div>
          <p className="mt-2 font-inter text-xs text-text-muted">
            {allConfigured
              ? "You can start chatting now or review your settings first."
              : "We'll skip the configured steps and only set up what's missing."}
          </p>
        </motion.div>
      )}

      <motion.div
        className="flex flex-col items-center gap-3"
        initial={shouldReduceMotion ? false : { opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.35, ease: [0.4, 0, 0.2, 1], delay: 0.24 }}
      >
        <button
          type="button"
          onClick={allConfigured ? onSkip : onContinue}
          className="px-8 py-2.5 rounded-lg bg-brand-700 text-white font-poppins text-sm font-semibold shadow-card-md transition-colors hover:bg-brand-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-brand-500"
        >
          {allConfigured ? "Go to chat" : isConfigured ? "Complete setup" : "Get started"}
        </button>
        <button
          type="button"
          onClick={allConfigured ? onContinue : onSkip}
          className="font-inter text-sm text-text-muted hover:text-text-primary transition-colors"
        >
          {allConfigured ? "Review settings" : "Skip setup for now"}
        </button>
      </motion.div>
    </div>
  );
};

export default WelcomeStep;
