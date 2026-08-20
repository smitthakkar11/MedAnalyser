import { useCallback, useState, type FormEvent } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FormAlert } from '@/components/FormAlert';
import { FormField } from '@/components/FormField';
import { GoogleButton } from '@/components/GoogleButton';
import { SubmitButton } from '@/components/SubmitButton';
import { useAuth } from '@/hooks/useAuth';
import { useGoogleSignIn } from '@/hooks/useGoogleSignIn';
import { ApiError } from '@/services/apiClient';
import { GOOGLE_LINK_REQUIRED } from '@/services/authService';

const PASSWORD_MIN_LENGTH = 10;

export function SignupPage() {
  const { signup, loginWithGoogle } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [pending, setPending] = useState(false);

  const handleGoogleCredential = useCallback(
    async (idToken: string) => {
      setError(null);
      try {
        const user = await loginWithGoogle(idToken);
        navigate(user.onboarding_complete ? '/dashboard' : '/onboarding', { replace: true });
      } catch (caught) {
        if (caught instanceof ApiError && caught.details['reason'] === GOOGLE_LINK_REQUIRED) {
          setError(
            'An account with this email address already exists. Sign in with your password instead, then link Google from your settings.',
          );
          return;
        }
        setError(
          caught instanceof ApiError ? caught.message : 'Google sign-up failed. Please try again.',
        );
      }
    },
    [loginWithGoogle, navigate],
  );

  const google = useGoogleSignIn({
    onCredential: handleGoogleCredential,
    onError: setError,
  });

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setFieldErrors({});
    setPending(true);
    try {
      await signup({ name, email, password });
      // A new account always goes to onboarding: the age check happens there.
      navigate('/onboarding', { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError) {
        const fields = caught.fieldErrors;
        if (Object.keys(fields).length > 0) {
          setFieldErrors(fields);
        } else {
          setError(caught.message);
        }
      } else {
        setError('Could not create your account. Please try again.');
      }
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-4xl font-bold tracking-tight">Create your account</h1>
        <p className="mt-2 text-ink-600 dark:text-ink-400">
          MedAnalyser is available to adults aged 18 and over.
        </p>
      </div>

      {error && <FormAlert message={error} />}

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <FormField
          label="Full name"
          name="name"
          autoComplete="name"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          error={fieldErrors['name']}
          placeholder="Ada Lovelace"
        />
        <FormField
          label="Email address"
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          error={fieldErrors['email']}
          placeholder="you@example.com"
        />
        <FormField
          label="Password"
          type="password"
          name="password"
          autoComplete="new-password"
          required
          minLength={PASSWORD_MIN_LENGTH}
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          error={fieldErrors['password']}
          hint={`At least ${PASSWORD_MIN_LENGTH} characters. A memorable phrase works well.`}
        />
        <SubmitButton pending={pending} pendingLabel="Creating account">
          Create account
        </SubmitButton>
      </form>

      <div className="flex items-center gap-4">
        <span className="h-px flex-1 bg-ink-200 dark:bg-ink-800" />
        <span className="text-xs font-medium uppercase tracking-wider text-ink-500">or</span>
        <span className="h-px flex-1 bg-ink-200 dark:bg-ink-800" />
      </div>

      <div className="space-y-2">
        <GoogleButton
          onClick={() => void google.start()}
          disabled={google.pending}
          label="Sign up with Google"
        />
        {!google.configured && (
          <p className="text-center text-xs text-ink-500">
            Google sign-in is not configured for this deployment.
          </p>
        )}
      </div>

      <p className="text-center text-sm text-ink-600 dark:text-ink-400">
        Already have an account?{' '}
        <Link to="/login" className="font-semibold text-ink-950 underline dark:text-ink-0">
          Sign in
        </Link>
      </p>
    </div>
  );
}
