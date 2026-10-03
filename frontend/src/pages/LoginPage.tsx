import { useState, type FormEvent } from 'react';
import { login } from '@/services/authApi';
import { useAuthStore } from '@/store/authStore';

const LoginPage = (): JSX.Element => {
  const [key, setKey] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const setStatus = useAuthStore((s) => s.setStatus);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (pending || key.length === 0) return;
    setError(null);
    setPending(true);
    try {
      await login(key);
      setKey('');
      setStatus('authenticated');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed');
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-base flex items-center justify-center px-6 3xl:px-8 4xl:px-10 py-12 3xl:py-16 4xl:py-20">
      <div className="w-full max-w-md 3xl:max-w-lg">
        <div className="bg-surface-card border border-border-ui rounded-xl p-8 3xl:p-10 shadow-modal">
          <h1 className="text-2xl 3xl:text-3xl font-poppins font-semibold text-text-primary mb-2">
            Access key required
          </h1>
          <p className="text-text-muted font-inter text-sm 3xl:text-base mb-6">
            This Cora instance is protected. Enter the instance access key to continue.
          </p>
          <form onSubmit={(e) => void handleSubmit(e)}>
            <label
              htmlFor="instance-access-key"
              className="block text-sm font-poppins font-medium text-text-primary mb-2"
            >
              Instance access key
            </label>
            <input
              id="instance-access-key"
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              autoComplete="current-password"
              autoFocus
              className="w-full px-4 3xl:px-5 py-3 3xl:py-4 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-sm 3xl:text-base focus:border-brand-700 focus:outline-none focus:ring-2 focus:ring-focus"
            />
            {error && (
              <div
                role="alert"
                className="mt-4 p-3 3xl:p-4 rounded-lg bg-semantic-error-bg border border-semantic-error-border text-semantic-error-text font-inter text-sm 3xl:text-base"
              >
                {error}
              </div>
            )}
            <button
              type="submit"
              disabled={pending || key.length === 0}
              className="mt-6 h-10 3xl:h-12 w-full rounded-lg bg-brand-700 px-4 font-inter text-sm 3xl:text-base font-semibold text-white transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-focus"
            >
              {pending ? 'Signing in...' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
