import { useCallback, useState, type FormEvent } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { FormAlert } from '@/components/FormAlert';
import { FormField } from '@/components/FormField';
import { GoogleButton } from '@/components/GoogleButton';
import { SubmitButton } from '@/components/SubmitButton';
import { useAuth } from '@/hooks/useAuth';
import { useGoogleSignIn } from '@/hooks/useGoogleSignIn';
import { ApiError } from '@/services/apiClient';
import { GOOGLE_LINK_REQUIRED } from '@/services/authService';

interface LocationState {
  from?: string;
}

export function LoginPage() {
  const { login, loginWithGoogle } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const destination = (location.state as LocationState | null)?.from;

  const goOnwards = useCallback(
    (onboardingComplete: boolean) => {
      if (!onboardingComplete) {
        navigate('/onboarding', { replace: true });
        return;
      }
      navigate(destination ?? '/dashboard', { replace: true });
    },
    [destination, navigate],
  );

  const handleGoogleCredential = useCallback(
    async (idToken: string) => {
      setError(null);
      try {
        const user = await loginWithGoogle(idToken);
        goOnwards(user.onboarding_complete);
      } catch (caught) {
        if (caught instanceof ApiError && caught.details['reason'] === GOOGLE_LINK_REQUIRED) {
          setError(
            'You already have an account with this email address. Sign in with your password below, then link Google from your settings.',
          );
          return;
        }
        setError(
          caught instanceof ApiError ? caught.message : 'Google sign-in failed. Please try again.',
        );
      }
    },
    [goOnwards, loginWithGoogle],
  );

  const google = useGoogleSignIn({
    onCredential: handleGoogleCredential,
    onError: setError,
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const user = await login({ email, password });
      goOnwards(user.onboarding_complete);
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Sign-in failed. Please try again.',
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">Welcome back</h1>
        <p className="mt-2 text-ink-600 dark:text-ink-400">
          Sign in to continue to your assessments.
        </p>
      </div>

      {error && <FormAlert message={error} />}

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <FormField
          label="Email address"
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="you@example.com"
        />
        <FormField
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <SubmitButton pending={pending} pendingLabel="Signing in">
          Sign in
        </SubmitButton>
      </form>

      <div className="flex items-center gap-4">
        <span className="h-px flex-1 bg-ink-200 dark:bg-ink-800" />
        <span className="text-xs font-medium uppercase tracking-wider text-ink-500">or</span>
        <span className="h-px flex-1 bg-ink-200 dark:bg-ink-800" />
      </div>

      <div className="space-y-2">
        <GoogleButton onClick={() => void google.start()} disabled={google.pending} />
        {!google.configured && (
          <p className="text-center text-xs text-ink-500">
            Google sign-in is not configured for this deployment.
          </p>
        )}
      </div>

      <p className="text-center text-sm text-ink-600 dark:text-ink-400">
        New to MedAnalyser?{' '}
        <Link to="/signup" className="font-semibold text-ink-950 underline dark:text-ink-0">
          Create an account
        </Link>
      </p>
    </div>
  );
}
