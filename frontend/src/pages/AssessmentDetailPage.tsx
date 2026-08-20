import { Link, useParams } from 'react-router-dom';
import { FormAlert } from '@/components/FormAlert';
import { FullPageSpinner } from '@/components/FullPageSpinner';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { PredictionCard } from '@/components/assessment/PredictionCard';
import { SymptomChips } from '@/components/assessment/SymptomChips';
import { useAsync } from '@/hooks/useAsync';
import { assessmentService } from '@/services/assessmentService';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}

interface FactProps {
  label: string;
  value: string | null;
}

function Fact({ label, value }: FactProps) {
  if (!value) return null;
  return (
    <div className="border-b border-ink-200 py-3 last:border-0 dark:border-ink-800">
      <dt className="text-sm text-ink-600 dark:text-ink-400">{label}</dt>
      <dd className="mt-0.5 font-medium">{value}</dd>
    </div>
  );
}

export function AssessmentDetailPage() {
  const { id = '' } = useParams();
  const { status, data, error } = useAsync(
    (signal) => assessmentService.get(id, signal),
    `assessment:${id}`,
  );

  if (status === 'loading') return <FullPageSpinner label="Loading assessment" />;
  if (status === 'error') {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <FormAlert message={error.message} />
        <Link to="/history" className="text-sm font-semibold underline">
          Back to history
        </Link>
      </div>
    );
  }

  const consultation =
    data.previous_consultation === null
      ? null
      : data.previous_consultation
        ? 'Yes'
        : 'No';

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <header>
        <p className="text-sm text-ink-500">{formatDate(data.created_at)}</p>
        <h1 className="mt-2 text-headline">
          {data.status === 'completed' ? 'Assessment result' : 'Assessment in progress'}
        </h1>
        <p className="mt-4 rounded-xl border border-ink-200 bg-ink-50/60 px-5 py-4 text-lg leading-relaxed dark:border-ink-800 dark:bg-ink-900/60">
          “{data.input_text}”
        </p>
      </header>

      {data.status !== 'completed' && (
        <div className="rounded-xl border border-ink-200 bg-ink-50/60 p-6 dark:border-ink-800 dark:bg-ink-900/60">
          <p className="font-semibold">This assessment was never finished.</p>
          <p className="mt-1 text-sm text-ink-600 dark:text-ink-400">
            No analysis was run, so there are no results to show.
          </p>
        </div>
      )}

      {data.status === 'completed' && (
        <section aria-labelledby="results-heading" className="space-y-5">
          <div className="border-b border-ink-950 pb-4 dark:border-ink-0">
            <h2 id="results-heading" className="text-2xl font-bold tracking-tight">
              Possible conditions
            </h2>
            <p className="mt-2 text-sm leading-relaxed text-ink-600 dark:text-ink-400">
              Ranked by model score. These are <strong>possibilities to discuss with a
              clinician</strong>, not a diagnosis, and the scores are relative model outputs
              rather than calibrated probabilities.
            </p>
          </div>

          {data.low_information && (
            <div
              role="note"
              className="rounded-xl border border-amber-200 bg-amber-50/70 px-5 py-4 text-sm leading-relaxed text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
            >
              Only {data.recognised_symptoms.length} symptom
              {data.recognised_symptoms.length === 1 ? ' was' : 's were'} recognised. The model
              is markedly less reliable on thin input.
            </div>
          )}

          {data.predictions.length > 0 ? (
            <ol className="space-y-4">
              {data.predictions.map((prediction, index) => (
                <PredictionCard
                  key={prediction.condition}
                  prediction={prediction}
                  rank={index + 1}
                />
              ))}
            </ol>
          ) : (
            <p className="rounded-xl border border-dashed border-ink-300 px-6 py-8 text-center text-sm text-ink-500 dark:border-ink-700">
              The model could not rank any condition from the symptoms it recognised.
            </p>
          )}
        </section>
      )}

      <section aria-labelledby="inputs-heading" className="space-y-5">
        <h2 id="inputs-heading" className="text-2xl font-bold tracking-tight">
          What this was based on
        </h2>

        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
            Symptoms used
          </p>
          <div className="mt-2">
            <SymptomChips
              symptoms={data.recognised_symptoms}
              emptyLabel="No symptoms were recognised."
            />
          </div>
        </div>

        {data.rejected_symptoms.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
              Ruled out
            </p>
            <div className="mt-2">
              <SymptomChips symptoms={data.rejected_symptoms} tone="negative" />
            </div>
          </div>
        )}

        <dl>
          <Fact
            label="Duration"
            value={data.duration_days ? `${data.duration_days} day(s)` : null}
          />
          <Fact label="Severity" value={data.severity} />
          <Fact label="Seen a doctor about this" value={consultation} />
          <Fact label="Previous diagnosis (as reported)" value={data.previous_diagnosis} />
          <Fact label="Previous medication (as reported)" value={data.previous_medication} />
          <Fact label="Did it help" value={data.treatment_response} />
        </dl>
      </section>

      {data.messages.length > 1 && (
        <section aria-labelledby="transcript-heading" className="space-y-4">
          <h2 id="transcript-heading" className="text-2xl font-bold tracking-tight">
            Conversation
          </h2>
          <ol className="space-y-3">
            {data.messages.map((message) => (
              <li
                key={message.id}
                className={
                  message.role === 'assistant'
                    ? 'max-w-lg rounded-2xl rounded-tl-sm border border-ink-200 px-4 py-3 text-sm dark:border-ink-800'
                    : 'ml-auto max-w-lg rounded-2xl rounded-tr-sm bg-ink-100 px-4 py-3 text-sm dark:bg-ink-900'
                }
              >
                {message.content}
              </li>
            ))}
          </ol>
        </section>
      )}

      {data.model_version && (
        <p className="text-xs text-ink-500">
          Produced by {data.model_name} {data.model_version}. Recorded so this result stays
          interpretable if the model changes.
        </p>
      )}

      <MedicalDisclaimer />

      <Link
        to="/history"
        className="inline-flex rounded-full border border-ink-300 px-5 py-2.5 text-sm font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
      >
        Back to history
      </Link>
    </div>
  );
}
