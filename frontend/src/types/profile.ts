/** Profile and dashboard contract types, mirroring the backend schemas. */

export type SexAtBirth = 'female' | 'male' | 'intersex' | 'prefer_not_to_say';
export type AllergySeverity = 'mild' | 'moderate' | 'severe' | 'unknown';
export type ConditionStatus = 'active' | 'managed' | 'resolved';

export interface AllergyInput {
  substance: string;
  reaction: string | null;
  severity: AllergySeverity;
}

export interface ConditionInput {
  name: string;
  status: ConditionStatus;
  diagnosed_year: number | null;
  notes: string | null;
}

export interface MedicationInput {
  name: string;
  dosage: string | null;
  frequency: string | null;
  started_on: string | null;
  is_current: boolean;
  notes: string | null;
}

export interface ProfileUpdate {
  sex_at_birth: SexAtBirth | null;
  gender_identity: string | null;
  notes: string | null;
  emergency_contact_name: string | null;
  emergency_contact_relationship: string | null;
  emergency_contact_phone: string | null;
  allergies: AllergyInput[];
  conditions: ConditionInput[];
  medications: MedicationInput[];
}

export interface Profile extends ProfileUpdate {
  date_of_birth: string | null;
  age: number | null;
  completeness: number;
}

export interface ProfileSummary {
  completeness: number;
  age: number | null;
  date_of_birth: string | null;
  allergy_count: number;
  condition_count: number;
  current_medication_count: number;
}

export interface Dashboard {
  user_name: string;
  profile: ProfileSummary;
  assessment_count: number;
  report_count: number;
}

export const SEX_AT_BIRTH_OPTIONS: { value: SexAtBirth; label: string }[] = [
  { value: 'female', label: 'Female' },
  { value: 'male', label: 'Male' },
  { value: 'intersex', label: 'Intersex' },
  { value: 'prefer_not_to_say', label: 'Prefer not to say' },
];

export const ALLERGY_SEVERITY_OPTIONS: { value: AllergySeverity; label: string }[] = [
  { value: 'unknown', label: 'Not sure' },
  { value: 'mild', label: 'Mild' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'severe', label: 'Severe' },
];

export const CONDITION_STATUS_OPTIONS: { value: ConditionStatus; label: string }[] = [
  { value: 'active', label: 'Active' },
  { value: 'managed', label: 'Managed' },
  { value: 'resolved', label: 'Resolved' },
];

export const EMPTY_ALLERGY: AllergyInput = {
  substance: '',
  reaction: null,
  severity: 'unknown',
};

export const EMPTY_CONDITION: ConditionInput = {
  name: '',
  status: 'active',
  diagnosed_year: null,
  notes: null,
};

export const EMPTY_MEDICATION: MedicationInput = {
  name: '',
  dosage: null,
  frequency: null,
  started_on: null,
  is_current: true,
  notes: null,
};
