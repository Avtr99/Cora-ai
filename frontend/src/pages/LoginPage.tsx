import { useState, type FormEvent } from 'react';
import { claimOwner, login } from '@/services/authApi';
import { useAuthStore } from '@/store/authStore';
import { passwordError } from '@/components/auth/passwordRule';
import { USERNAME_HINT, usernameError } from '@/components/auth/usernameRule';
import PasswordInput from '@/components/ui/PasswordInput';

const inputClass =
  'w-full px-4 3xl:px-5 py-3 3xl:py-4 rounded-lg border border-border-ui bg-surface-card text-text-primary font-inter text-sm 3xl:text-base focus:border-brand-700 focus:outline-hidden focus:ring-2 focus:ring-focus';
const labelClass =
  'block text-sm font-poppins font-medium text-text-primary mb-2';
const submitClass =
  'mt-6 h-10 3xl:h-12 w-full rounded-lg bg-brand-700 px-4 font-inter text-sm 3xl:text-base font-semibold text-white transition-colors hover:bg-brand-hover disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-focus';
const linkClass =
  'mt-4 w-full text-center font-inter text-sm 3xl:text-base text-text-muted hover:text-text-primary transition-colors rounded-sm focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus';

const LoginPage = (): JSX.Element => {
  const ownerClaimRequired = useAuthStore((s) => s.ownerClaimRequired);
  const applySession = useAuthStore((s) => s.applySession);

  // The owner-claim form shows first while the owner account is unclaimed;
  // a link switches back to sign-in.
  const [mode, setMode] = useState<'claim' | 'signin'>(
    ownerClaimRequired ? 'claim' : 'signin'
  );

  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [accessKey, setAccessKey] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const switchMode = (next: 'claim' | 'signin') => {
    setMode(next);
    setError(null);
  };

  const handleSignIn = async (e: FormEvent) => {
    e.preventDefault();
    if (pending || !username || !password) return;
    // Client-side checks only — the server stays the authority.
    const nameError = usernameError(username);
    if (nameError) {
      setError(nameError);
      return;
    }
    setError(null);
    setPending(true);
    try {
      const session = await login(username, password);
      applySession(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Sign-in failed');
    } finally {
      setPending(false);
    }
  };

  const handleClaim = async (e: FormEvent) => {
    e.preventDefault();
    if (pending || !accessKey || !username || !password) return;
    // Client-side checks only — the server stays the authority.
    const nameError = usernameError(username);
    if (nameError) {
      setError(nameError);
      return;
    }
    const ruleError = passwordError(password);
    if (ruleError) {
      setError(ruleError);
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }
    setError(null);
    setPending(true);
    try {
      const session = await claimOwner(accessKey, username, password);
      applySession(session);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Setup failed');
    } finally {
      setPending(false);
    }
  };

  return (
    <div className="min-h-screen bg-surface-base flex items-center justify-center px-6 3xl:px-8 4xl:px-10 py-12 3xl:py-16 4xl:py-20">
      <div className="w-full max-w-md 3xl:max-w-lg">
        <div className="bg-surface-card border border-border-ui rounded-xl p-8 3xl:p-10 shadow-modal">
          {mode === 'signin' ? (
            <>
              <h1 className="text-2xl 3xl:text-3xl font-poppins font-semibold text-text-primary mb-2">
                Sign in
              </h1>
              <p className="text-text-muted font-inter text-sm 3xl:text-base mb-6">
                This Cora instance is protected. Sign in with your account to continue.
              </p>
              <form onSubmit={(e) => void handleSignIn(e)}>
                <label htmlFor="login-username" className={labelClass}>
                  Username
                </label>
                <input
                  id="login-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  autoFocus
                  className={inputClass}
                />
                <p className="mt-1.5 text-xs 3xl:text-sm text-text-muted font-inter">
                  {USERNAME_HINT}
                </p>
                <label htmlFor="login-password" className={`${labelClass} mt-4`}>
                  Password
                </label>
                <PasswordInput
                  id="login-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  className={inputClass}
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
                  disabled={pending || !username || !password}
                  className={submitClass}
                >
                  {pending ? 'Signing in...' : 'Sign in'}
                </button>
              </form>
              {ownerClaimRequired && (
                <button
                  type="button"
                  onClick={() => switchMode('claim')}
                  className={linkClass}
                >
                  First time here? Set up the owner account
                </button>
              )}
            </>
          ) : (
            <>
              <h1 className="text-2xl 3xl:text-3xl font-poppins font-semibold text-text-primary mb-2">
                Set up owner account
              </h1>
              <p className="text-text-muted font-inter text-sm 3xl:text-base mb-6">
                No owner exists yet. Enter the instance access key once, then choose
                your username and password.
              </p>
              <form onSubmit={(e) => void handleClaim(e)}>
                <label htmlFor="claim-access-key" className={labelClass}>
                  Instance access key
                </label>
                <PasswordInput
                  id="claim-access-key"
                  value={accessKey}
                  onChange={(e) => setAccessKey(e.target.value)}
                  autoComplete="off"
                  autoFocus
                  className={inputClass}
                />
                <label htmlFor="claim-username" className={`${labelClass} mt-4`}>
                  Username
                </label>
                <input
                  id="claim-username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  className={inputClass}
                />
                <p className="mt-1.5 text-xs 3xl:text-sm text-text-muted font-inter">
                  {USERNAME_HINT}
                </p>
                <label htmlFor="claim-password" className={`${labelClass} mt-4`}>
                  Password
                </label>
                <PasswordInput
                  id="claim-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  className={inputClass}
                />
                <label htmlFor="claim-password-confirm" className={`${labelClass} mt-4`}>
                  Confirm password
                </label>
                <PasswordInput
                  id="claim-password-confirm"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  autoComplete="new-password"
                  className={inputClass}
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
                  disabled={
                    pending || !accessKey || !username || !password || !confirmPassword
                  }
                  className={submitClass}
                >
                  {pending ? 'Setting up...' : 'Create owner account'}
                </button>
              </form>
              <button
                type="button"
                onClick={() => switchMode('signin')}
                className={linkClass}
              >
                Already have an account? Sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
