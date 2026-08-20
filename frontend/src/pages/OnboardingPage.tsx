import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { FormAlert } from '@/components/FormAlert';
import { FormField } from '@/components/FormField';
import { SubmitButton } from '@/components/SubmitButton';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/services/apiClient';
import { authService } from '@/services/authService';

const AGE_RESTRICTED = 'age_requirement_not_met';

/** Today, as YYYY-MM-DD, for the date input's upper bound. */
function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

export function OnboardingPage() {
  const { user, setUser, logout } = useAuth();
  const navigate = useNavigate();

  const [dateOfBirth, setDateOfBirth] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [ageRestricted, setAgeRestricted] = useState(false);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const updated = await authService.completeOnboarding(dateOfBirth);
      setUser(updated);
      navigate('/dashboard', { replace: true });
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === AGE_RESTRICTED) {
        // A dedicated state, not a form error: this is a hard stop.
        setAgeRestricted(true);
        return;
      }
      if (caught instanceof ApiError) {
        setError(caught.fieldErrors['date_of_birth'] ?? caught.message);
        return;
      }
      setError('Could not save your date of birth. Please try again.');
    } finally {
      setPending(false);
    }
  }

  if (ageRestricted) {
    return (
      <div className="space-y-6">
        <div className="inline-flex rounded-2xl bg-gradient-to-br from-accent-amber to-accent-magenta p-3 text-white">
          <svg
            viewBox="0 0 24 24"
            className="size-6"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <circle cx="12" cy="12" r="9" />
            <path d="M12 8v5M12 16h.01" />
          </svg>
        </div>
        <h1 className="text-3xl font-bold tracking-tight">MedAnalyser is for adults</h1>
        <p className="leading-relaxed text-ink-600 dark:text-ink-400">
          Based on the date of birth you entered, you are under 18. MedAnalyser is designed for
          adults and cannot be used by younger people.
        </p>
        <p className="leading-relaxed text-ink-600 dark:text-ink-400">
          If you are unwell, please speak to a parent, carer, or a doctor. In an emergency,
          contact your local emergency services immediately.
        </p>
        <button
          type="button"
          onClick={() => void logout().then(() => navigate('/', { replace: true }))}
          className="rounded-xl border border-ink-300 px-6 py-3 text-sm font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
        >
          Return to home
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <p className="text-sm font-semibold text-accent-violet">Step 1 of 1</p>
        <h1 className="mt-2 text-4xl font-bold tracking-tight">
          {user ? `Welcome, ${user.name.split(' ')[0]}` : 'Welcome'}
        </h1>
        <p className="mt-2 leading-relaxed text-ink-600 dark:text-ink-400">
          We need your date of birth to confirm you are 18 or over, and because age affects how
          symptoms and lab results are interpreted.
        </p>
      </div>

      {error && <FormAlert message={error} />}

      <form onSubmit={handleSubmit} noValidate className="space-y-5">
        <FormField
          label="Date of birth"
          type="date"
          name="date_of_birth"
          autoComplete="bday"
          required
          max={todayIso()}
          value={dateOfBirth}
          onChange={(event) => setDateOfBirth(event.target.value)}
        />
        <SubmitButton pending={pending} pendingLabel="Saving">
          Continue
        </SubmitButton>
      </form>

      <p className="text-xs leading-relaxed text-ink-500">
        Your date of birth is stored with your account and used only to interpret your health
        information. It is never shared.
      </p>
    </div>
  );
}
