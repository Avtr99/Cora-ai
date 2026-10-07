import { useEffect, type ReactNode } from 'react';
import { getSession } from '@/services/authApi';
import { useAuthStore } from '@/store/authStore';
import { PageLoader } from '@/components/PageLoader';
import LoginPage from '@/pages/LoginPage';

/**
 * Gates the SPA on the username/password session. On mount it asks the
 * backend whether auth is required; while unknown it shows the page loader,
 * while required it shows the login page on every route. A rejected
 * getSession (backend down, or an older backend without the route) maps to
 * 'open' so the app shows its own backend-down state — the server still
 * enforces auth regardless.
 */
export function AuthGate({ children }: { children: ReactNode }): JSX.Element {
  const status = useAuthStore((s) => s.status);

  useEffect(() => {
    let cancelled = false;
    getSession()
      .then((session) => {
        if (cancelled) return;
        useAuthStore.getState().applySession(session);
      })
      .catch(() => {
        if (cancelled) return;
        useAuthStore.getState().setStatus('open');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (status === 'unknown') {
    return <PageLoader />;
  }
  if (status === 'required') {
    return <LoginPage />;
  }
  return <>{children}</>;
}
