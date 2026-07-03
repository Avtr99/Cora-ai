import { lazy, Suspense, type ReactNode, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import { DocumentHead } from "@/components/ui/DocumentHead";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import NotFound from "@/pages/NotFound";
import { getLLMSettings } from "@/services/llmSettingsApi";
import { ONBOARDING_COMPLETE_KEY } from "@/components/onboarding/onboardingState";

// Lazy-load heavy pages to reduce initial bundle size
const HomePage = lazy(() => import("@/pages/HomePage"));
const CaseStudyPage = lazy(() => import("@/pages/CaseStudyPage"));
const CaseStudiesPage = lazy(() => import("@/pages/CaseStudiesPage"));
const PricingPage = lazy(() => import("@/pages/PricingPage"));
const AboutPage = lazy(() => import("@/pages/AboutPage"));
const ProjectsPage = lazy(() => import("@/pages/ProjectsPage"));
const DocumentStorePage = lazy(() => import("@/pages/DocumentStorePage"));
const SetupPage = lazy(() => import("@/pages/SetupPage"));
const OnboardingPage = lazy(() => import("@/pages/OnboardingPage"));
const PrivacyPolicyPage = lazy(() => import("@/pages/PrivacyPolicyPage"));
const TermsOfServicePage = lazy(() => import("@/pages/TermsOfServicePage"));
const CookiePolicyPage = lazy(() => import("@/pages/CookiePolicyPage"));

// Lazy-load @tanstack/react-query + the query client together so pricing
// / case-study pages never pay for them.
const DataProviders = lazy(() => import("@/providers/DataProviders"));

// Loading fallback for lazy-loaded pages
function PageLoader(): JSX.Element {
  return (
    <div className="min-h-screen bg-surface-base flex items-center justify-center">
      <div className="animate-pulse text-text-muted font-inter text-sm">Loading...</div>
    </div>
  );
}

/** Wrap every top-level route so a component crash doesn't bring down the whole SPA. */
function Safe({ children }: { children: ReactNode }): JSX.Element {
  return <ErrorBoundary fallback="This page failed to load. Please try reloading.">{children}</ErrorBoundary>;
}

/** Stable wrapper component for routes that need react-query. */
function WithData({ children }: { children: ReactNode }): JSX.Element {
  return <DataProviders>{children}</DataProviders>;
}

/**
 * First-run redirect: if the LLM isn't configured and the user hasn't
 * completed/dismissed onboarding, send them to /onboarding on first visit
 * to the home route.
 *
 * Robustness: if the backend is unreachable, we still redirect on the very
 * first visit (detected via a separate localStorage "has visited" flag) so
 * the user sees the onboarding wizard even without a running backend. On
 * subsequent visits, if the backend is down, we don't re-trigger onboarding
 * (the user has already seen it or dismissed it).
 */
const VISITED_KEY = "cora_has_visited";

function FirstRunRedirect(): null {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if (location.pathname !== "/") return;

    let onboardingDone = false;
    let hasVisited = false;
    try {
      onboardingDone = localStorage.getItem(ONBOARDING_COMPLETE_KEY) === "true";
      hasVisited = localStorage.getItem(VISITED_KEY) === "true";
    } catch {
      /* localStorage unavailable — treat as first visit */
    }

    // Mark as visited immediately so we don't re-trigger on every render
    try {
      localStorage.setItem(VISITED_KEY, "true");
    } catch {
      /* non-fatal */
    }

    if (onboardingDone) return;

    let cancelled = false;
    getLLMSettings()
      .then((s) => {
        if (cancelled) return;
        if (!s.is_configured) {
          navigate("/onboarding", { replace: true });
        }
      })
      .catch(() => {
        // Backend unreachable: only redirect on the very first visit
        // (hasVisited === false). On subsequent visits, let the user stay
        // on the chat page — the chat will show its own error state.
        if (!hasVisited) {
          navigate("/onboarding", { replace: true });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [location.pathname, navigate]);

  return null;
}

function App(): JSX.Element {
  // Preload all route chunks after initial render so navigation feels instant.
  // Uses requestIdleCallback when available to avoid blocking the main thread.
  useEffect(() => {
    const preloadAll = () => {
      const routes = [
        () => import("@/pages/HomePage"),
        () => import("@/pages/ProjectsPage"),
        () => import("@/pages/DocumentStorePage"),
        () => import("@/pages/AboutPage"),
        () => import("@/pages/CaseStudyPage"),
        () => import("@/pages/CaseStudiesPage"),
        () => import("@/pages/PricingPage"),
        () => import("@/providers/DataProviders"),
      ];
      for (const loader of routes) {
        loader().catch((err) => console.error("[Preload] Failed to load:", err));
      }
    };

    if (typeof requestIdleCallback !== "undefined") {
      requestIdleCallback(preloadAll, { timeout: 3000 });
    } else {
      setTimeout(preloadAll, 2000);
    }
  }, []);

  return (
    <BrowserRouter>
      <DocumentHead />
      <FirstRunRedirect />
      <Suspense fallback={<PageLoader />}>
        <Routes>
          {/* Setup / Settings / Onboarding routes (no data providers needed). */}
          <Route path="/onboarding/" element={<Safe><OnboardingPage /></Safe>} />
          <Route path="/onboarding" element={<Navigate to="/onboarding/" replace />} />
          <Route path="/setup/" element={<Safe><SetupPage /></Safe>} />
          <Route path="/setup" element={<Navigate to="/setup/" replace />} />
          <Route path="/settings/" element={<Safe><SetupPage /></Safe>} />
          <Route path="/settings" element={<Navigate to="/settings/" replace />} />
          {/* Data routes (use @tanstack/react-query). */}
          <Route path="/" element={<Safe><WithData><HomePage /></WithData></Safe>} />
          <Route path="/projects/" element={<Safe><WithData><ProjectsPage /></WithData></Safe>} />
          <Route path="/projects" element={<Navigate to="/projects/" replace />} />
          <Route path="/documents/" element={<Safe><WithData><DocumentStorePage /></WithData></Safe>} />
          <Route path="/documents" element={<Navigate to="/documents/" replace />} />
          <Route path="/about/" element={<Safe><WithData><AboutPage /></WithData></Safe>} />
          <Route path="/about" element={<Navigate to="/about/" replace />} />
          {/* Static routes (no data fetching). */}
          <Route path="/case-studies/" element={<Safe><CaseStudiesPage /></Safe>} />
          <Route path="/case-studies" element={<Navigate to="/case-studies/" replace />} />
          <Route path="/case-study/:id/" element={<Safe><CaseStudyPage /></Safe>} />
          <Route path="/case-study/" element={<Navigate to="/case-study/mangrove-myanmar/" replace />} />
          <Route path="/case-study" element={<Navigate to="/case-study/mangrove-myanmar/" replace />} />
          <Route path="/pricing/" element={<Safe><PricingPage /></Safe>} />
          <Route path="/pricing" element={<Navigate to="/pricing/" replace />} />
          {/* Legal / Policy pages */}
          <Route path="/privacy-policy/" element={<Safe><PrivacyPolicyPage /></Safe>} />
          <Route path="/privacy-policy" element={<Navigate to="/privacy-policy/" replace />} />
          <Route path="/terms-of-service/" element={<Safe><TermsOfServicePage /></Safe>} />
          <Route path="/terms-of-service" element={<Navigate to="/terms-of-service/" replace />} />
          <Route path="/cookie-policy/" element={<Safe><CookiePolicyPage /></Safe>} />
          <Route path="/cookie-policy" element={<Navigate to="/cookie-policy/" replace />} />
          {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
          <Route path="*" element={<Safe><NotFound /></Safe>} />
        </Routes>
      </Suspense>
    </BrowserRouter>
  );
}

export default App;
