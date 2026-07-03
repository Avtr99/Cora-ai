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
  "w-full px-4 py-2.5 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-sm focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-200";

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
      <label className="block text-sm font-poppins font-medium text-text-primary mb-1.5">
        {label}
        {hint && <span className="ml-2 text-xs text-semantic-success-icon font-normal">{hint}</span>}
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
    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
      {(Object.keys(presets) as T[]).map((key) => (
        <button
          key={key}
          type="button"
          onClick={() => onSelect(key)}
          className={`px-3 py-2 rounded-lg border text-xs font-poppins font-medium transition-all ${
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
        className="px-4 py-2 rounded-lg border border-border-ui bg-surface-card text-text-primary font-poppins text-sm font-medium transition-colors hover:bg-surface-subtle disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {state === "testing" ? "Testing..." : "Test connection"}
      </button>

      {state === "success" && result && (
        <div className="mt-3 p-3 rounded-lg bg-semantic-success-bg border border-semantic-success-border text-semantic-success-text font-inter text-sm flex items-start gap-2">
          <span className="text-semantic-success-icon font-bold flex-shrink-0">{"\u2713"}</span>
          <div className="font-medium">{result.message}</div>
        </div>
      )}

      {state === "failed" && result && (
        <div className="mt-3 p-3 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-sm flex items-start gap-2">
          <span className="text-semantic-error-icon font-bold flex-shrink-0">{"\u2717"}</span>
          <div>
            <div className="font-medium">{result.message}</div>
            {result.detail && (
              <details className="mt-1">
                <summary className="text-xs text-semantic-error-text cursor-pointer">Show detail</summary>
                <div className="mt-1 text-xs text-semantic-error-icon font-mono break-all">{result.detail}</div>
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
    <div className="p-3 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-sm">
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
    <div className="flex items-center gap-3 pt-1">
      <button
        type="button"
        onClick={onSave}
        disabled={saving}
        className="px-5 py-2.5 rounded-lg bg-brand-700 text-white font-poppins text-sm font-semibold shadow-card-md transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {saving ? "Saving..." : label}
      </button>
      <button
        type="button"
        onClick={onCancel}
        className="px-5 py-2.5 rounded-lg border border-border-ui text-text-secondary font-poppins text-sm font-medium transition-colors hover:bg-surface-subtle"
      >
        Cancel
      </button>
    </div>
  );
}

/** Green success banner shown after a successful save. */
export function SavedBanner({ text }: { text: string }): JSX.Element {
  return (
    <div className="py-8 text-center">
      <div className="text-4xl text-semantic-success-icon mb-3">{"\u2713"}</div>
      <p className="font-poppins text-lg font-semibold text-text-primary">Settings saved</p>
      <p className="font-inter text-sm text-text-muted mt-1">{text}</p>
    </div>
  );
}
