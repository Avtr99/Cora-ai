/**
 * Shared UI primitives for settings forms.
 *
 * Used by SettingsDialog and the onboarding steps to keep form fields,
 * test-connection UI, save/cancel buttons, and error/success banners
 * visually consistent without duplicating markup.
 */

import { AlertTriangle, Check, CheckCircle2, X } from "lucide-react";
import type { LLMTestResult } from "@/services/llmSettingsApi";

export type TestState = "idle" | "testing" | "success" | "failed";

const FOCUS_RING =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-2";

/** Shared input class string — matches the design system (fixed h-9 controls). */
export const inputClass =
  "w-full h-9 3xl:h-11 4xl:h-12 px-3 3xl:px-4 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-body-sm 3xl:text-base 4xl:text-lg focus:border-border-strong focus:outline-hidden focus:ring-2 focus:ring-focus";

/** Labeled form field with optional hint badge and wrapper className. */
export function Field({
  label,
  hint,
  className,
  children,
}: {
  label: string;
  hint?: string;
  className?: string;
  children: React.ReactNode;
}): JSX.Element {
  return (
    <div className={className}>
      <label className="block text-body-sm 3xl:text-base 4xl:text-lg font-poppins font-medium text-text-primary mb-1.5 3xl:mb-2 4xl:mb-3">
        {label}
        {hint && <span className="ml-2 text-caption 3xl:text-sm 4xl:text-base text-semantic-success-text font-normal">{hint}</span>}
      </label>
      {children}
    </div>
  );
}

const GRID_COLUMNS = {
  2: "sm:grid-cols-2",
  3: "sm:grid-cols-3",
  4: "sm:grid-cols-4",
} as const;

const GRID_SIZES = {
  compact: {
    grid: "gap-2 3xl:gap-3 4xl:gap-4",
    button: "px-3 3xl:px-4 py-1.5 3xl:py-2 4xl:py-2.5 text-ui 3xl:text-sm 4xl:text-base",
  },
  roomy: {
    grid: "gap-3 3xl:gap-4 4xl:gap-5",
    button: "px-4 3xl:px-5 py-3 3xl:py-4 4xl:py-5 text-body-sm 3xl:text-base 4xl:text-lg",
  },
} as const;

/** Provider selection button grid (works with any preset record). */
export function ProviderGrid<T extends string>({
  presets,
  selected,
  onSelect,
  columns = 3,
  size = "compact",
  descriptions = false,
}: {
  presets: Record<T, { label: string; description?: string }>;
  selected: T;
  onSelect: (key: T) => void;
  /** Column count at the sm breakpoint and up (base is always 2). */
  columns?: 2 | 3 | 4;
  /** compact = settings dialog density; roomy = onboarding density. */
  size?: "compact" | "roomy";
  /** Render each preset's description as a subtitle inside the card. */
  descriptions?: boolean;
}): JSX.Element {
  const sizing = GRID_SIZES[size];
  return (
    <div className={`grid grid-cols-2 ${GRID_COLUMNS[columns]} ${sizing.grid}`}>
      {(Object.keys(presets) as T[]).map((key) => {
        const preset = presets[key];
        const isActive = selected === key;
        return (
          <button
            key={key}
            type="button"
            aria-pressed={isActive}
            onClick={() => onSelect(key)}
            className={`${sizing.button} rounded-lg border font-poppins font-medium transition-all ${FOCUS_RING} ${
              descriptions ? "text-left" : ""
            } ${
              isActive
                ? "border-text-primary bg-surface-subtle text-text-primary shadow-xs"
                : "border-border-ui bg-surface-card text-text-secondary hover:border-border-strong hover:bg-surface-subtle"
            }`}
          >
            {descriptions ? (
              <>
                <span className="block font-semibold">{preset.label}</span>
                <span className="mt-0.5 3xl:mt-1 block font-inter font-normal text-caption 3xl:text-sm 4xl:text-base text-text-muted">
                  {preset.description}
                </span>
              </>
            ) : (
              preset.label
            )}
          </button>
        );
      })}
    </div>
  );
}

/** Test connection button + success/failure result display. */
export function TestConnection({
  state,
  result,
  onTest,
}: {
  state: TestState;
  result: LLMTestResult | null;
  onTest: () => void;
}): JSX.Element {
  return (
    <div>
      <button
        type="button"
        onClick={onTest}
        disabled={state === "testing"}
        className={`inline-flex h-9 3xl:h-10 4xl:h-11 items-center px-4 3xl:px-5 rounded-lg border border-border-ui bg-surface-card text-text-primary font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-medium transition-colors hover:border-text-muted hover:bg-surface-subtle disabled:opacity-50 disabled:cursor-not-allowed ${FOCUS_RING}`}
      >
        {state === "testing" ? "Testing..." : "Test connection"}
      </button>

      {state === "success" && result && (
        <div className="mt-3 3xl:mt-4 p-3 3xl:p-4 4xl:p-5 rounded-lg bg-semantic-success-bg border border-semantic-success-border text-semantic-success-text font-inter text-body-sm 3xl:text-base 4xl:text-lg flex items-start gap-2 3xl:gap-3">
          <Check className="mt-0.5 h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 text-semantic-success-icon" strokeWidth={2.5} aria-hidden="true" />
          <div className="font-medium">{result.message}</div>
        </div>
      )}

      {state === "failed" && result && (
        <div className="mt-3 3xl:mt-4 p-3 3xl:p-4 4xl:p-5 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-body-sm 3xl:text-base 4xl:text-lg flex items-start gap-2 3xl:gap-3">
          <X className="mt-0.5 h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 text-semantic-error-icon" strokeWidth={2.5} aria-hidden="true" />
          <div>
            <div className="font-medium">{result.message}</div>
            {result.detail && (
              <details className="mt-1 3xl:mt-2">
                <summary className="text-caption 3xl:text-sm 4xl:text-base text-semantic-error-text cursor-pointer">Show detail</summary>
                <div className="mt-1 3xl:mt-2 text-caption 3xl:text-sm 4xl:text-base text-semantic-error-text font-mono break-all">{result.detail}</div>
              </details>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/** Red error box for form submission errors. */
export function ErrorBox({ message }: { message: string }): JSX.Element {
  return (
    <div className="p-3 3xl:p-4 4xl:p-5 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-body-sm 3xl:text-base 4xl:text-lg flex items-start gap-2 3xl:gap-3">
      <AlertTriangle className="mt-0.5 h-4 w-4 3xl:h-5 3xl:w-5 shrink-0 text-semantic-error-icon" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

/** Save + Cancel button pair. */
export function SaveCancel({
  onSave,
  onCancel,
  saving,
  label = "Save",
}: {
  onSave: () => void;
  onCancel: () => void;
  saving: boolean;
  label?: string;
}): JSX.Element {
  return (
    <div className="flex items-center gap-3 3xl:gap-4 4xl:gap-5 pt-1">
      <button
        type="button"
        onClick={onSave}
        disabled={saving}
        className={`inline-flex h-9 3xl:h-10 4xl:h-11 items-center px-4 3xl:px-5 rounded-lg bg-brand-700 text-white font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-semibold shadow-card-md transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed ${FOCUS_RING}`}
      >
        {saving ? "Saving..." : label}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className={`inline-flex h-9 3xl:h-10 4xl:h-11 items-center px-4 3xl:px-5 rounded-lg border border-border-ui text-text-secondary font-poppins text-body-sm 3xl:text-base 4xl:text-lg font-medium transition-colors hover:border-text-muted hover:bg-surface-subtle ${FOCUS_RING}`}
      >
        Cancel
      </button>
    </div>
  );
}

/** Green success banner shown after a successful save. */
export function SavedBanner({ text }: { text: string }): JSX.Element {
  return (
    <div className="py-6 3xl:py-8 4xl:py-10 text-center">
      <CheckCircle2 className="mx-auto mb-2.5 3xl:mb-3 4xl:mb-4 h-8 w-8 3xl:h-10 3xl:w-10 4xl:h-12 4xl:w-12 text-semantic-success-icon" strokeWidth={2} aria-hidden="true" />
      <p className="font-poppins text-heading-2 3xl:text-xl 4xl:text-2xl font-semibold text-text-primary">Settings saved</p>
      <p className="font-inter text-body-sm 3xl:text-base 4xl:text-lg text-text-muted mt-1 3xl:mt-2">{text}</p>
    </div>
  );
}
