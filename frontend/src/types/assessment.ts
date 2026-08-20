/** Assessment contract types, mirroring the backend schemas. */

export type AssessmentStatus = 'in_progress' | 'completed';

export type AnswerType =
  | 'text'
  | 'choice'
  | 'boolean'
  | 'number'
  | 'duration'
  | 'symptom_check';

export interface SymptomOption {
  value: string;
  label: string;
}

export interface FollowUpQuestion {
  key: string;
  text: string;
  answer_type: AnswerType;
  help_text: string | null;
  choices: string[];
  symptom_options: SymptomOption[];
}

export interface Prediction {
  condition: string;
  /** Relative model score — NOT a calibrated probability. */
  score: number;
  contributing_symptoms: string[];
}

export interface AssessmentMessage {
  id: string;
  role: 'assistant' | 'user';
  question_key: string | null;
  content: string;
  created_at: string;
}

export interface AssessmentDetail {
  id: string;
  status: AssessmentStatus;
  input_text: string;
  recognised_symptoms: string[];
  rejected_symptoms: string[];
  unrecognised_terms: string[];
  duration_days: number | null;
  severity: string | null;
  previous_consultation: boolean | null;
  previous_diagnosis: string | null;
  previous_medication: string | null;
  treatment_response: string | null;
  still_taking_medication: boolean | null;
  predictions: Prediction[];
  model_name: string | null;
  model_version: string | null;
  messages: AssessmentMessage[];
  next_question: FollowUpQuestion | null;
  low_information: boolean;
  created_at: string;
  completed_at: string | null;
}

export interface AssessmentSummary {
  id: string;
  status: AssessmentStatus;
  input_text: string;
  top_condition: string | null;
  symptom_count: number;
  created_at: string;
  completed_at: string | null;
}

export type AnswerValue = string | boolean | number | string[] | null;

/** `abdominal_pain` → `Abdominal pain`. */
export function humaniseSymptom(symptom: string): string {
  const spaced = symptom.replace(/_/g, ' ');
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * Turn a model score into a qualitative band.
 *
 * The product never shows a raw percentage: the score is a relative model
 * output with no calibration behind it, and a number like "72%" reads as a
 * clinical probability to anyone who is worried.
 */
export function scoreBand(score: number): 'high' | 'moderate' | 'low' {
  if (score >= 0.5) return 'high';
  if (score >= 0.2) return 'moderate';
  return 'low';
}
