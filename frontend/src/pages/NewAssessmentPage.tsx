import { useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { FormAlert } from '@/components/FormAlert';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { SubmitButton } from '@/components/SubmitButton';
import { AnswerControl } from '@/components/assessment/AnswerControl';
import { SymptomChips } from '@/components/assessment/SymptomChips';
import { ApiError } from '@/services/apiClient';
import { assessmentService } from '@/services/assessmentService';
import type { AnswerValue, AssessmentDetail } from '@/types/assessment';

const EXAMPLES = [
  "I've had a headache and been throwing up for 3 days",
  'Stomach ache and loose motions since yesterday',
  'High temperature, chills and body aches',
] as const;

export function NewAssessmentPage() {
  const navigate = useNavigate();
  const [text, setText] = useState('');
  const [assessment, setAssessment] = useState<AssessmentDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function start(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      setAssessment(await assessmentService.create(text));
    } catch (caught) {
      setError(
        caught instanceof ApiError ? caught.message : 'Could not start the assessment.',
      );
    } finally {
      setPending(false);
    }
  }

  async function answer(value: AnswerValue) {
    if (!assessment?.next_question) return;
    setError(null);
    setPending(true);
    try {
      setAssessment(
        await assessmentService.answer(assessment.id, assessment.next_question.key, value),
      );
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not save your answer.');
    } finally {
      setPending(false);
    }
  }

  async function analyse() {
    if (!assessment) return;
    setError(null);
    setPending(true);
    try {
      const completed = await assessmentService.analyse(assessment.id);
      navigate(`/assessment/${completed.id}`, { replace: true });
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : 'Could not run the analysis.');
    } finally {
      setPending(false);
    }
  }

  // ------------------------------------------------------------- step one
  if (!assessment) {
    return (
      <div className="max-w-2xl space-y-8">
        <header>
          <h1 className="text-headline">What's troubling you?</h1>
          <p className="mt-3 text-lg text-ink-600 dark:text-ink-400">
            Describe your symptoms in your own words. MedAnalyser will read them, ask a few
            follow-up questions, and suggest what might be worth discussing with a doctor.
          </p>
        </header>

        {error && <FormAlert message={error} />}

        <form onSubmit={start} noValidate className="space-y-4">
          <label htmlFor="symptom-text" className="block text-sm font-semibold">
            Your symptoms
          </label>
          <textarea
            id="symptom-text"
            rows={5}
            maxLength={2000}
            required
            value={text}
            onChange={(event) => setText(event.target.value)}
            placeholder="For example: I've had a headache and been throwing up for 3 days"
            className="w-full rounded-xl border border-ink-300 bg-ink-0 px-4 py-3 text-base transition placeholder:text-ink-400 focus:outline-none focus-visible:border-ink-950 focus-visible:ring-2 focus-visible:ring-ink-950/15 dark:border-ink-700 dark:bg-ink-900 dark:focus-visible:border-ink-0 dark:focus-visible:ring-ink-0/20"
          />
          <div className="max-w-xs">
            <SubmitButton pending={pending} pendingLabel="Reading">
              Continue
            </SubmitButton>
          </div>
        </form>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
            Not sure how to phrase it?
          </p>
          <ul className="mt-3 space-y-2">
            {EXAMPLES.map((example) => (
              <li key={example}>
                <button
                  type="button"
                  onClick={() => setText(example)}
                  className="text-left text-sm text-ink-600 underline decoration-ink-300 underline-offset-4 transition hover:text-ink-950 dark:text-ink-400 dark:hover:text-ink-0"
                >
                  “{example}”
                </button>
              </li>
            ))}
          </ul>
        </div>

        <MedicalDisclaimer />
      </div>
    );
  }

  // ------------------------------------------------------- step two onwards
  const question = assessment.next_question;

  return (
    <div className="max-w-2xl space-y-8">
      <header>
        <h1 className="text-3xl font-bold tracking-tight">
          {question ? 'A few more details' : 'Ready to analyse'}
        </h1>
        <p className="mt-2 text-ink-600 dark:text-ink-400">
          {question
            ? 'Each answer helps narrow things down. You can skip anything you are unsure about.'
            : 'MedAnalyser has what it needs.'}
        </p>
      </header>

      <section
        aria-label="What was understood"
        className="rounded-2xl border border-ink-200 bg-ink-50/60 p-5 dark:border-ink-800 dark:bg-ink-900/60"
      >
        <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
          Symptoms understood
        </p>
        <div className="mt-3">
          <SymptomChips
            symptoms={assessment.recognised_symptoms}
            emptyLabel="Nothing recognised yet — the questions below will help."
          />
        </div>
        {assessment.rejected_symptoms.length > 0 && (
          <div className="mt-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
              Ruled out
            </p>
            <div className="mt-2">
              <SymptomChips symptoms={assessment.rejected_symptoms} tone="negative" />
            </div>
          </div>
        )}
        {assessment.unrecognised_terms.length > 0 && (
          <p className="mt-4 text-xs text-ink-500">
            Not recognised: {assessment.unrecognised_terms.join(', ')}. MedAnalyser only knows a
            fixed list of symptoms — anything else is ignored rather than guessed at.
          </p>
        )}
      </section>

      {error && <FormAlert message={error} />}

      {question ? (
        <section aria-live="polite" className="space-y-5">
          <div>
            <h2 className="text-xl font-semibold">{question.text}</h2>
            {question.help_text && (
              <p className="mt-2 text-sm leading-relaxed text-ink-600 dark:text-ink-400">
                {question.help_text}
              </p>
            )}
          </div>
          <AnswerControl
            // Remount per question so the previous answer never bleeds through.
            // A repeated question key still remounts because the turn count moves.
            key={`${question.key}-${assessment.messages.length}`}
            question={question}
            onSubmit={(value) => void answer(value)}
            pending={pending}
          />
        </section>
      ) : (
        <section className="space-y-5">
          {assessment.low_information && (
            <div
              role="note"
              className="rounded-xl border border-amber-200 bg-amber-50/70 px-5 py-4 text-sm leading-relaxed text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
            >
              Only a few symptoms were recognised. The model is markedly less reliable on thin
              input, so treat anything it suggests with extra caution.
            </div>
          )}
          <button
            type="button"
            disabled={pending}
            onClick={() => void analyse()}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent-blue to-accent-violet px-8 py-3.5 text-base font-semibold text-white shadow-lg shadow-accent-violet/20 transition hover:shadow-xl hover:shadow-accent-violet/35 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pending && (
              <span
                aria-hidden="true"
                className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
              />
            )}
            {pending ? 'Analysing…' : 'Analyse my symptoms'}
          </button>
        </section>
      )}

      <MedicalDisclaimer />
    </div>
  );
}
