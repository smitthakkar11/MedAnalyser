import { FormField } from '@/components/FormField';
import { RepeatableList } from '@/components/RepeatableList';
import { Select } from '@/components/Select';
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
  type ProfileUpdate,
  type SexAtBirth,
} from '@/types/profile';

/**
 * Field groups for the medical profile.
 *
 * Shared by the onboarding wizard and the profile page so the two can never
 * drift — same labels, same validation affordances, same wording about what
 * each field is for.
 */

type ListUpdater<T> = (update: (items: T[]) => T[]) => void;

const todayIso = () => new Date().toISOString().slice(0, 10);

interface AboutYouProps {
  sexAtBirth: SexAtBirth | null;
  genderIdentity: string | null;
  onChange: (patch: Partial<ProfileUpdate>) => void;
}

export function AboutYouFields({ sexAtBirth, genderIdentity, onChange }: AboutYouProps) {
  return (
    <>
      <Select
        label="Sex at birth"
        value={sexAtBirth}
        options={SEX_AT_BIRTH_OPTIONS}
        placeholder="Prefer not to answer"
        onValueChange={(value) => onChange({ sex_at_birth: value })}
      />
      <FormField
        label="Gender identity (optional)"
        value={genderIdentity ?? ''}
        onChange={(event) => onChange({ gender_identity: event.target.value })}
        placeholder="How you describe your gender"
      />
    </>
  );
}

export function AllergiesEditor({
  items,
  onChange,
}: {
  items: AllergyInput[];
  onChange: ListUpdater<AllergyInput>;
}) {
  return (
    <RepeatableList<AllergyInput>
      items={items}
      onChange={onChange}
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
  );
}

export function ConditionsEditor({
  items,
  onChange,
}: {
  items: ConditionInput[];
  onChange: ListUpdater<ConditionInput>;
}) {
  return (
    <RepeatableList<ConditionInput>
      items={items}
      onChange={onChange}
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
            onValueChange={(status) => update({ status: status ?? 'active' })}
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
  );
}

export function MedicationsEditor({
  items,
  onChange,
}: {
  items: MedicationInput[];
  onChange: ListUpdater<MedicationInput>;
}) {
  return (
    <RepeatableList<MedicationInput>
      items={items}
      onChange={onChange}
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
            max={todayIso()}
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
  );
}

interface EmergencyContactProps {
  name: string | null;
  relationship: string | null;
  phone: string | null;
  onChange: (patch: Partial<ProfileUpdate>) => void;
}

export function EmergencyContactFields({
  name,
  relationship,
  phone,
  onChange,
}: EmergencyContactProps) {
  return (
    <>
      <FormField
        label="Name"
        value={name ?? ''}
        onChange={(event) => onChange({ emergency_contact_name: event.target.value })}
      />
      <FormField
        label="Relationship"
        value={relationship ?? ''}
        onChange={(event) =>
          onChange({ emergency_contact_relationship: event.target.value })
        }
        placeholder="Partner, sibling, friend"
      />
      <FormField
        label="Phone"
        type="tel"
        value={phone ?? ''}
        onChange={(event) => onChange({ emergency_contact_phone: event.target.value })}
      />
    </>
  );
}

export function NotesField({
  value,
  onChange,
}: {
  value: string | null;
  onChange: (patch: Partial<ProfileUpdate>) => void;
}) {
  return (
    <textarea
      aria-label="Additional notes"
      rows={5}
      maxLength={2000}
      value={value ?? ''}
      onChange={(event) => onChange({ notes: event.target.value })}
      className="w-full rounded-xl border border-ink-300 bg-ink-0 px-4 py-3 text-base transition placeholder:text-ink-400 focus:outline-none focus-visible:border-ink-950 focus-visible:ring-2 focus-visible:ring-ink-950/15 dark:border-ink-700 dark:bg-ink-900 dark:focus-visible:border-ink-0 dark:focus-visible:ring-ink-0/20"
      placeholder="Recent surgery, family history, anything you think matters."
    />
  );
}
