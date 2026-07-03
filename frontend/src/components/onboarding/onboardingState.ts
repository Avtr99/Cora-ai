/**
 * Onboarding completion state — persisted in localStorage so the first-run
 * redirect in App.tsx doesn't re-trigger after the user finishes or skips
 * the wizard.
 *
 * Kept in its own module (rather than exported from OnboardingPage.tsx) so
 * that React Fast Refresh stays happy: OnboardingPage only exports a
 * component, and this file only exports constants/functions.
 */

/** localStorage key recording that the user finished or dismissed onboarding. */
export const ONBOARDING_COMPLETE_KEY = "cora_onboarding_complete";

/** Mark onboarding as complete so the first-run redirect won't re-trigger. */
export function markOnboardingComplete(): void {
  try {
    localStorage.setItem(ONBOARDING_COMPLETE_KEY, "true");
  } catch {
    /* localStorage may be unavailable (private mode) — non-fatal */
  }
}

/** Has the user already completed or dismissed onboarding? */
export function isOnboardingComplete(): boolean {
  try {
    return localStorage.getItem(ONBOARDING_COMPLETE_KEY) === "true";
  } catch {
    return false;
  }
}
