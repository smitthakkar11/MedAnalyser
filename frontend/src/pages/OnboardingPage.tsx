import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { FormAlert } from '@/components/FormAlert';
import { FormField } from '@/components/FormField';
import { StepProgress } from '@/components/StepProgress';
import { SubmitButton } from '@/components/SubmitButton';
import {
  AboutYouFields,
  AllergiesEditor,
  ConditionsEditor,
  EmergencyContactFields,
  MedicationsEditor,
  NotesField,
} from '@/components/profile/editors';
import { FullPageSpinner } from '@/components/FullPageSpinner';
import { useAsync } from '@/hooks/useAsync';
import { useAuth } from '@/hooks/useAuth';
import { ApiError } from '@/services/apiClient';
import { authService } from '@/services/authService';
import { profileService } from '@/services/profileService';
import type { Profile, ProfileUpdate } from '@/types/profile';

const AGE_RESTRICTED = 'age_requirement_not_met';

const EMPTY_PROFILE: ProfileUpdate = {
  sex_at_birth: null,
  gender_identity: null,
  notes: null,
  emergency_contact_name: null,
  emergency_contact_relationship: null,
  emergency_contact_phone: null,
  allergies: [],
  conditions: [],
  medications: [],
};

interface Step {
  id: string;
  title: string;
  description: string;
  /** Required steps cannot be skipped. Only the age check is required. */
  required: boolean;
}

const STEPS: readonly Step[] = [
  {
    id: 'dob',
    title: 'Your date of birth',
    description:
      'MedAnalyser is for adults aged 18 and over, and age changes how symptoms and lab results are interpreted. This is the only answer we need.',
    required: true,
  },
  {
    id: 'about',
    title: 'About you',
    description:
      'Sex at birth affects laboratory reference ranges and the likelihood of many conditions, so it changes how results are read. Gender identity is recorded separately and is never used for that.',
    required: false,
  },
  {
    id: 'allergies',
    title: 'Any allergies?',
    description:
      'Medicines, foods, materials — anything you react to. This is checked against any medication information MedAnalyser shows you.',
    required: false,
  },
  {
    id: 'conditions',
    title: 'Existing conditions',
    description:
      'Anything you have been diagnosed with. Recorded as your own account of your history, kept separate from anything MedAnalyser concludes itself.',
    required: false,
  },
  {
    id: 'medications',
    title: 'Medications you take',
    description:
      'Exactly as prescribed to you. MedAnalyser records what you write and never suggests, changes or calculates a dose.',
    required: false,
  },
  {
    id: 'extras',
    title: 'Emergency contact and notes',
    description:
      'Who to contact if you needed help, plus anything else a clinician would want to know. Stored with your account and never shared.',
    required: false,
  },
] as const;

const todayIso = () => new Date().toISOString().slice(0, 10);

/** Strip response-only fields so the draft matches what PUT expects. */
function toUpdate(profile: Profile): ProfileUpdate {
  return {
    sex_at_birth: profile.sex_at_birth,
    gender_identity: profile.gender_identity,
    notes: profile.notes,
    emergency_contact_name: profile.emergency_contact_name,
    emergency_contact_relationship: profile.emergency_contact_relationship,
    emergency_contact_phone: profile.emergency_contact_phone,
    allergies: profile.allergies,
    conditions: profile.conditions,
    medications: profile.medications,
  };
}

export function OnboardingPage() {
  const { user, setUser } = useAuth();
  const navigate = useNavigate();

  // A returning user who already passed the age check resumes after step one.
  const resuming = user?.onboarding_complete ?? false;
  const [stepIndex, setStepIndex] = useState(resuming ? 1 : 0);
  const [dateOfBirth, setDateOfBirth] = useState(user?.date_of_birth ?? '');
  const [draft, setDraft] = useState<ProfileUpdate>(EMPTY_PROFILE);
  const [seededFrom, setSeededFrom] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [ageRestricted, setAgeRestricted] = useState(false);
  const [pending, setPending] = useState(false);

  // A resuming user's existing answers must be loaded before anything is saved.
  // Finishing here PUTs the whole profile, so starting from a blank draft would
  // wipe whatever they had already recorded. Brand-new users skip this: their
  // profile is empty anyway, and the endpoint refuses them until the age check
  // has passed.
  const existing = useAsync<Profile | null>(
    (signal) => (resuming ? profileService.getProfile(signal) : Promise.resolve(null)),
    resuming ? 'onboarding:existing-profile' : 'onboarding:new-user',
  );

  if (existing.status === 'success' && existing.data && seededFrom !== existing.data) {
    setSeededFrom(existing.data);
    setDraft(toUpdate(existing.data));
  }

  const step = STEPS[stepIndex]!;
  const isLastStep = stepIndex === STEPS.length - 1;

  const patch = (changes: Partial<ProfileUpdate>) =>
    setDraft((current) => ({ ...current, ...changes }));

  function patchList<K extends 'allergies' | 'conditions' | 'medications'>(
    key: K,
    update: (items: ProfileUpdate[K]) => ProfileUpdate[K],
  ) {
    setDraft((current) => ({ ...current, [key]: update(current[key]) }));
  }

  /** Persist the accumulated profile. Skipped answers are simply absent. */
  async function saveProfile(): Promise<boolean> {
    try {
      await profileService.updateProfile(draft);
      return true;
    } catch (caught) {
      setError(
        caught instanceof ApiError
          ? caught.message
          : 'Could not save your details. Please try again.',
      );
      return false;
    }
  }

  async function submitDateOfBirth(): Promise<boolean> {
    try {
      const updated = await authService.completeOnboarding(dateOfBirth);
      setUser(updated);
      return true;
    } catch (caught) {
      if (caught instanceof ApiError && caught.code === AGE_RESTRICTED) {
        setAgeRestricted(true);
        return false;
      }
      setError(
        caught instanceof ApiError
          ? (caught.fieldErrors['date_of_birth'] ?? caught.message)
          : 'Could not save your date of birth. Please try again.',
      );
      return false;
    }
  }

  async function advance() {
    setError(null);
    setPending(true);
    try {
      if (step.id === 'dob' && !(await submitDateOfBirth())) return;
      if (isLastStep) {
        if (!(await saveProfile())) return;
        navigate('/dashboard', { replace: true });
        return;
      }
      setStepIndex((index) => index + 1);
    } finally {
      setPending(false);
    }
  }

  /** Leave the rest for later, keeping whatever has been entered so far. */
  async function finishEarly() {
    setError(null);
    setPending(true);
    try {
      if (!(await saveProfile())) return;
      navigate('/dashboard', { replace: true });
    } finally {
      setPending(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void advance();
  }

  // Never render the form before a resuming user's answers have loaded — a save
  // from a blank draft would delete them.
  if (resuming && existing.status === 'loading') {
    return <FullPageSpinner label="Loading your details" />;
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
          onClick={() => navigate('/', { replace: true })}
          className="rounded-xl border border-ink-300 px-6 py-3 text-sm font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
        >
          Return to home
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <StepProgress
        current={stepIndex}
        total={STEPS.length}
        label={step.required ? 'Required' : 'Optional'}
      />

      <div>
        {stepIndex === 0 && user && (
          <p className="text-sm font-semibold text-ink-500">
            Welcome, {user.name.split(' ')[0]}
          </p>
        )}
        <h1 className="mt-1 text-3xl font-bold tracking-tight sm:text-4xl">{step.title}</h1>
        <p className="mt-3 leading-relaxed text-ink-600 dark:text-ink-400">
          {step.description}
        </p>
      </div>

      {error && <FormAlert message={error} />}

      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        {step.id === 'dob' && (
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
        )}

        {step.id === 'about' && (
          <AboutYouFields
            sexAtBirth={draft.sex_at_birth}
            genderIdentity={draft.gender_identity}
            onChange={patch}
          />
        )}

        {step.id === 'allergies' && (
          <AllergiesEditor
            items={draft.allergies}
            onChange={(update) => patchList('allergies', update)}
          />
        )}

        {step.id === 'conditions' && (
          <ConditionsEditor
            items={draft.conditions}
            onChange={(update) => patchList('conditions', update)}
          />
        )}

        {step.id === 'medications' && (
          <MedicationsEditor
            items={draft.medications}
            onChange={(update) => patchList('medications', update)}
          />
        )}

        {step.id === 'extras' && (
          <div className="space-y-5">
            <EmergencyContactFields
              name={draft.emergency_contact_name}
              relationship={draft.emergency_contact_relationship}
              phone={draft.emergency_contact_phone}
              onChange={patch}
            />
            <NotesField value={draft.notes} onChange={patch} />
          </div>
        )}

        <div className="space-y-3 pt-2">
          <SubmitButton pending={pending} pendingLabel="Saving">
            {isLastStep ? 'Finish' : 'Continue'}
          </SubmitButton>

          {!step.required && (
            <div className="flex flex-wrap items-center justify-between gap-3">
              <button
                type="button"
                disabled={pending}
                onClick={() => void advance()}
                className="rounded-lg px-2 py-1 text-sm font-semibold text-ink-600 transition hover:text-ink-950 disabled:opacity-50 dark:text-ink-400 dark:hover:text-ink-0"
              >
                Skip this question
              </button>
              <button
                type="button"
                disabled={pending}
                onClick={() => void finishEarly()}
                className="rounded-lg px-2 py-1 text-sm font-medium text-ink-500 underline transition hover:text-ink-950 disabled:opacity-50 dark:hover:text-ink-0"
              >
                Skip the rest for now
              </button>
            </div>
          )}
        </div>
      </form>

      <p className="text-xs leading-relaxed text-ink-500">
        {step.required
          ? 'Your date of birth is stored with your account and used only to interpret your health information.'
          : 'Everything after your date of birth is optional. You can add or change any of it later from your profile.'}
      </p>
    </div>
  );
}
