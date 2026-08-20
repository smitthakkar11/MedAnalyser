import { useState, type FormEvent } from 'react';
import { FormAlert } from '@/components/FormAlert';
import { FormField } from '@/components/FormField';
import { FullPageSpinner } from '@/components/FullPageSpinner';
import { RepeatableList } from '@/components/RepeatableList';
import { Select } from '@/components/Select';
import { SubmitButton } from '@/components/SubmitButton';
import { useAsync } from '@/hooks/useAsync';
import { ApiError } from '@/services/apiClient';
import { profileService } from '@/services/profileService';
import {
  ALLERGY_SEVERITY_OPTIONS,
  CONDITION_STATUS_OPTIONS,
  EMPTY_ALLERGY,
  EMPTY_CONDITION,
  EMPTY_MEDICATION,
  SEX_AT_BIRTH_OPTIONS,
  type AllergyInput,
  type ConditionInput,
  type MedicationInput,
  type Profile,
  type ProfileUpdate,
} from '@/types/profile';

/** Strip response-only fields so the payload matches what PUT expects. */
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

interface SectionProps {
  title: string;
  description: string;
  children: React.ReactNode;
}

function Section({ title, description, children }: SectionProps) {
  return (
    <section className="grid gap-6 border-t border-ink-200 py-10 lg:grid-cols-[1fr_2fr] lg:gap-12 dark:border-ink-800">
      <div>
        <h2 className="text-xl font-bold tracking-tight">{title}</h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-600 dark:text-ink-400">
          {description}
        </p>
      </div>
      <div className="space-y-5">{children}</div>
    </section>
  );
}

export function ProfilePage() {
  const { status, data, error, reload } = useAsync(
    (signal) => profileService.getProfile(signal),
    'profile',
  );

  const [draft, setDraft] = useState<ProfileUpdate | null>(null);
  const [seededFrom, setSeededFrom] = useState<Profile | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);

  // Seed the editable draft from the loaded profile. Adjusting state during
  // render is React's sanctioned pattern for deriving state from changing
  // input; doing it in an effect would cost an extra render pass every load.
  if (status === 'success' && seededFrom !== data) {
    setSeededFrom(data);
    setDraft(toUpdate(data));
  }

  if (status === 'loading' || (status === 'success' && !draft)) {
    return <FullPageSpinner label="Loading your profile" />;
  }

  if (status === 'error') {
    return (
      <div className="max-w-lg space-y-4">
        <FormAlert message={error.message} />
        <button
          type="button"
          onClick={reload}
          className="rounded-full border border-ink-300 px-5 py-2.5 text-sm font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
        >
          Try again
        </button>
      </div>
    );
  }

  if (!draft) return null;

  /**
   * Apply a change to the draft.
   *
   * Functional form on purpose: several fields can be edited before React
   * re-renders, and spreading a captured `draft` would silently discard all but
   * the last of them.
   */
  const patch = (changes: Partial<ProfileUpdate>) => {
    setDraft((current) => (current ? { ...current, ...changes } : current));
    setSaved(false);
  };

  /** Apply an updater to one of the collections, against current state. */
  function patchList<K extends 'allergies' | 'conditions' | 'medications'>(
    key: K,
    update: (items: ProfileUpdate[K]) => ProfileUpdate[K],
  ) {
    setDraft((current) => (current ? { ...current, [key]: update(current[key]) } : current));
    setSaved(false);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft) return;
    setSaveError(null);
    setSaved(false);
    setPending(true);
    try {
      const updated = await profileService.updateProfile(draft);
      setDraft(toUpdate(updated));
      setSaved(true);
    } catch (caught) {
      setSaveError(
        caught instanceof ApiError ? caught.message : 'Could not save your profile.',
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="max-w-5xl">
      <header className="pb-2">
        <h1 className="text-headline">Your medical profile</h1>
        <p className="mt-3 max-w-2xl text-lg text-ink-600 dark:text-ink-400">
          This is the background MedAnalyser considers alongside every symptom you describe and
          every report you upload. Everything here is optional — but the more it knows, the more
          useful its questions become.
        </p>
      </header>

      {saveError && (
        <div className="mt-6">
          <FormAlert message={saveError} />
        </div>
      )}

      {saved && (
        <div
          role="status"
          className="mt-6 rounded-xl border border-emerald-500/40 bg-emerald-500/8 px-4 py-3 text-sm"
        >
          Profile saved.
        </div>
      )}

      <form onSubmit={handleSubmit} noValidate>
        <Section
          title="About you"
          description="Sex at birth affects laboratory reference ranges and the likelihood of many conditions, so it changes how results are read. Gender identity is recorded separately and is never used for that."
        >
          <Select
            label="Sex at birth"
            value={draft.sex_at_birth}
            options={SEX_AT_BIRTH_OPTIONS}
            placeholder="Prefer not to answer"
            onValueChange={(value) => patch({ sex_at_birth: value })}
          />
          <FormField
            label="Gender identity (optional)"
            value={draft.gender_identity ?? ''}
            onChange={(event) => patch({ gender_identity: event.target.value })}
            placeholder="How you describe your gender"
          />
          <div className="rounded-xl border border-ink-200 bg-ink-50/60 px-4 py-3 text-sm dark:border-ink-800 dark:bg-ink-900/60">
            <span className="text-ink-600 dark:text-ink-400">Date of birth</span>
            <span className="ml-2 font-semibold">{data.date_of_birth ?? '—'}</span>
            {data.age !== null && (
              <span className="ml-2 text-ink-500">({data.age} years)</span>
            )}
          </div>
        </Section>

        <Section
          title="Allergies"
          description="Anything you react to — medicines, foods, materials. This is checked against any medication information MedAnalyser shows you."
        >
          <RepeatableList<AllergyInput>
            items={draft.allergies}
            onChange={(update) => patchList('allergies', update)}
            emptyItem={EMPTY_ALLERGY}
            addLabel="Add an allergy"
            removeLabel="Remove allergy"
            emptyMessage="No allergies recorded."
            renderItem={(item, update) => (
              <>
                <FormField
                  label="Substance"
                  required
                  value={item.substance}
                  onChange={(event) => update({ substance: event.target.value })}
                  placeholder="Penicillin"
                />
                <FormField
                  label="Reaction (optional)"
                  value={item.reaction ?? ''}
                  onChange={(event) => update({ reaction: event.target.value })}
                  placeholder="Hives, swelling"
                />
                <Select
                  label="Severity"
                  value={item.severity}
                  options={ALLERGY_SEVERITY_OPTIONS}
                  onValueChange={(severity) => update({ severity: severity ?? 'unknown' })}
                />
              </>
            )}
          />
        </Section>

        <Section
          title="Existing conditions"
          description="Conditions you have been diagnosed with. Recorded as your own account of your history — MedAnalyser keeps that separate from anything it concludes itself."
        >
          <RepeatableList<ConditionInput>
            items={draft.conditions}
            onChange={(update) => patchList('conditions', update)}
            emptyItem={EMPTY_CONDITION}
            addLabel="Add a condition"
            removeLabel="Remove condition"
            emptyMessage="No conditions recorded."
            renderItem={(item, update) => (
              <>
                <FormField
                  label="Condition"
                  required
                  value={item.name}
                  onChange={(event) => update({ name: event.target.value })}
                  placeholder="Asthma"
                />
                <Select
                  label="Status"
                  value={item.status}
                  options={CONDITION_STATUS_OPTIONS}
                  onValueChange={(statusValue) => update({ status: statusValue ?? 'active' })}
                />
                <FormField
                  label="Year diagnosed (optional)"
                  type="number"
                  inputMode="numeric"
                  min={1900}
                  max={new Date().getFullYear()}
                  value={item.diagnosed_year ?? ''}
                  onChange={(event) =>
                    update({
                      diagnosed_year: event.target.value ? Number(event.target.value) : null,
                    })
                  }
                />
                <FormField
                  label="Notes (optional)"
                  value={item.notes ?? ''}
                  onChange={(event) => update({ notes: event.target.value })}
                />
              </>
            )}
          />
        </Section>

        <Section
          title="Current medications"
          description="What you take, exactly as prescribed to you. MedAnalyser records this as written — it never suggests, changes or calculates a dose."
        >
          <RepeatableList<MedicationInput>
            items={draft.medications}
            onChange={(update) => patchList('medications', update)}
            emptyItem={EMPTY_MEDICATION}
            addLabel="Add a medication"
            removeLabel="Remove medication"
            emptyMessage="No medications recorded."
            renderItem={(item, update) => (
              <>
                <FormField
                  label="Medication"
                  required
                  value={item.name}
                  onChange={(event) => update({ name: event.target.value })}
                  placeholder="Salbutamol"
                />
                <FormField
                  label="Dose (optional)"
                  value={item.dosage ?? ''}
                  onChange={(event) => update({ dosage: event.target.value })}
                  placeholder="100 mcg"
                />
                <FormField
                  label="How often (optional)"
                  value={item.frequency ?? ''}
                  onChange={(event) => update({ frequency: event.target.value })}
                  placeholder="Twice daily"
                />
                <FormField
                  label="Started (optional)"
                  type="date"
                  max={new Date().toISOString().slice(0, 10)}
                  value={item.started_on ?? ''}
                  onChange={(event) => update({ started_on: event.target.value || null })}
                />
                <label className="flex items-center gap-3 text-sm font-medium sm:col-span-2">
                  <input
                    type="checkbox"
                    checked={item.is_current}
                    onChange={(event) => update({ is_current: event.target.checked })}
                    className="size-4 rounded border-ink-300 dark:border-ink-700"
                  />
                  I am still taking this
                </label>
              </>
            )}
          />
        </Section>

        <Section
          title="Emergency contact"
          description="Who to contact if you needed help. Stored with your account and never shared."
        >
          <FormField
            label="Name"
            value={draft.emergency_contact_name ?? ''}
            onChange={(event) => patch({ emergency_contact_name: event.target.value })}
          />
          <FormField
            label="Relationship"
            value={draft.emergency_contact_relationship ?? ''}
            onChange={(event) =>
              patch({ emergency_contact_relationship: event.target.value })
            }
            placeholder="Partner, sibling, friend"
          />
          <FormField
            label="Phone"
            type="tel"
            value={draft.emergency_contact_phone ?? ''}
            onChange={(event) => patch({ emergency_contact_phone: event.target.value })}
          />
        </Section>

        <Section
          title="Anything else"
          description="Context that does not fit above but that a clinician would want to know."
        >
          <textarea
            aria-label="Additional notes"
            rows={5}
            maxLength={2000}
            value={draft.notes ?? ''}
            onChange={(event) => patch({ notes: event.target.value })}
            className="w-full rounded-xl border border-ink-300 bg-ink-0 px-4 py-3 text-base transition placeholder:text-ink-400 focus:outline-none focus-visible:border-ink-950 focus-visible:ring-2 focus-visible:ring-ink-950/15 dark:border-ink-700 dark:bg-ink-900 dark:focus-visible:border-ink-0 dark:focus-visible:ring-ink-0/20"
            placeholder="Recent surgery, family history, anything you think matters."
          />
        </Section>

        <div className="sticky bottom-0 border-t border-ink-200 bg-ink-0/90 py-5 backdrop-blur-md dark:border-ink-800 dark:bg-ink-950/90">
          <div className="max-w-xs">
            <SubmitButton pending={pending} pendingLabel="Saving">
              Save profile
            </SubmitButton>
          </div>
        </div>
      </form>
    </div>
  );
}
