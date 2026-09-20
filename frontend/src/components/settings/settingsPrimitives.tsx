/**
 * Shared UI primitives for settings forms.
 *
 * Used by SettingsDialog and the onboarding steps to keep form fields,
 * test-connection UI, save/cancel buttons, and error/success banners
 * visually consistent without duplicating markup.
 */

import type { LLMTestResult } from "@/services/llmSettingsApi";

export type TestState = "idle" | "testing" | "success" | "failed";

/** Shared input class string — matches the design system. */
export const inputClass =
  "w-full px-4 3xl:px-5 py-2.5 3xl:py-3 4xl:py-4 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-sm 3xl:text-base 4xl:text-lg focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-focus";

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
      <label className="block text-sm 3xl:text-base 4xl:text-lg font-poppins font-medium text-text-primary mb-1.5 3xl:mb-2 4xl:mb-3">
        {label}
        {hint && <span className="ml-2 text-xs 3xl:text-sm 4xl:text-base text-semantic-success-icon font-normal">{hint}</span>}
      </label>
      {children}
    </div>
  );
}

/** Provider selection button grid (works with any preset record). */
export function ProviderGrid<T extends string>({
  presets,
  selected,
  onSelect,
}: {
  presets: Record<T, { label: string }>;
  selected: T;
  onSelect: (key: T) => void;
}): JSX.Element {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 3xl:gap-3 4xl:gap-4">
      {(Object.keys(presets) as T[]).map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => onSelect(key)}
          className={`px-3 3xl:px-4 py-2 3xl:py-2.5 4xl:py-3 rounded-lg border text-xs 3xl:text-sm 4xl:text-base font-poppins font-medium transition-all ${
            selected === key
              ? "border-brand-700 bg-brand-50 text-brand-700"
              : "border-border-ui bg-surface-card text-text-secondary hover:border-brand-300 hover:bg-surface-subtle"
          }`}
        >
          {presets[key].label}
        </button>
      ))}
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
        className="px-4 3xl:px-5 py-2 3xl:py-2.5 4xl:py-3 rounded-lg border border-border-ui bg-surface-card text-text-primary font-poppins text-sm 3xl:text-base 4xl:text-lg font-medium transition-colors hover:bg-surface-subtle disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {state === "testing" ? "Testing..." : "Test connection"}
      </button>

      {state === "success" && result && (
        <div className="mt-3 3xl:mt-4 p-3 3xl:p-4 4xl:p-5 rounded-lg bg-semantic-success-bg border border-semantic-success-border text-semantic-success-text font-inter text-sm 3xl:text-base 4xl:text-lg flex items-start gap-2 3xl:gap-3">
          <span className="text-semantic-success-icon font-bold flex-shrink-0">{"\u2713"}</span>
          <div className="font-medium">{result.message}</div>
        </div>
      )}

      {state === "failed" && result && (
        <div className="mt-3 3xl:mt-4 p-3 3xl:p-4 4xl:p-5 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-sm 3xl:text-base 4xl:text-lg flex items-start gap-2 3xl:gap-3">
          <span className="text-semantic-error-icon font-bold flex-shrink-0">{"\u2717"}</span>
          <div>
            <div className="font-medium">{result.message}</div>
            {result.detail && (
              <details className="mt-1 3xl:mt-2">
                <summary className="text-xs 3xl:text-sm 4xl:text-base text-semantic-error-text cursor-pointer">Show detail</summary>
                <div className="mt-1 3xl:mt-2 text-xs 3xl:text-sm 4xl:text-base text-semantic-error-icon font-mono break-all">{result.detail}</div>
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
    <div className="p-3 3xl:p-4 4xl:p-5 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-sm 3xl:text-base 4xl:text-lg">
      {message}
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
        className="px-5 3xl:px-6 py-2.5 3xl:py-3 4xl:py-4 rounded-lg bg-brand-700 text-white font-poppins text-sm 3xl:text-base 4xl:text-lg font-semibold shadow-card-md transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {saving ? "Saving..." : label}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="px-5 3xl:px-6 py-2.5 3xl:py-3 4xl:py-4 rounded-lg border border-border-ui text-text-secondary font-poppins text-sm 3xl:text-base 4xl:text-lg font-medium transition-colors hover:bg-surface-subtle"
      >
        Cancel
      </button>
    </div>
  );
}

/** Green success banner shown after a successful save. */
export function SavedBanner({ text }: { text: string }): JSX.Element {
  return (
    <div className="py-8 3xl:py-10 4xl:py-12 text-center">
      <div className="text-4xl 3xl:text-5xl 4xl:text-6xl text-semantic-success-icon mb-3 3xl:mb-4 4xl:mb-5">{"\u2713"}</div>
      <p className="font-poppins text-lg 3xl:text-xl 4xl:text-2xl font-semibold text-text-primary">Settings saved</p>
      <p className="font-inter text-sm 3xl:text-base 4xl:text-lg text-text-muted mt-1 3xl:mt-2">{text}</p>
    </div>
  );
}
