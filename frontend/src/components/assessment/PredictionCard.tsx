import { humaniseSymptom, scoreBand, type Prediction } from '@/types/assessment';

interface PredictionCardProps {
  prediction: Prediction;
  rank: number;
}

const BAND_LABEL: Record<ReturnType<typeof scoreBand>, string> = {
  high: 'Higher model score',
  moderate: 'Moderate model score',
  low: 'Lower model score',
};

const BAND_STYLE: Record<ReturnType<typeof scoreBand>, string> = {
  high: 'from-accent-teal to-accent-blue',
  moderate: 'from-accent-blue to-accent-violet',
  low: 'from-ink-400 to-ink-500',
};

/**
 * One candidate condition.
 *
 * The raw score is deliberately not shown as a percentage: it is an uncalibrated
 * relative output, and "72%" reads as a clinical probability to a worried
 * person. A qualitative band plus a bar conveys the ranking without implying
 * precision the model does not have.
 */
export function PredictionCard({ prediction, rank }: PredictionCardProps) {
  const band = scoreBand(prediction.score);

  return (
    <li className="rounded-2xl border border-ink-200 bg-ink-0 p-6 dark:border-ink-800 dark:bg-ink-950">
      <div className="flex items-start justify-between gap-4">
        <div>
          <span className="font-mono text-xs text-ink-500">
            {String(rank).padStart(2, '0')}
          </span>
          <h3 className="mt-1 text-xl font-bold tracking-tight">{prediction.condition}</h3>
        </div>
        <span className="shrink-0 text-xs font-semibold text-ink-600 dark:text-ink-400">
          {BAND_LABEL[band]}
        </span>
      </div>

      <div
        className="mt-4 h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800"
        role="img"
        aria-label={`${BAND_LABEL[band]} for ${prediction.condition}`}
      >
        <div
          className={`h-full rounded-full bg-gradient-to-r ${BAND_STYLE[band]}`}
          style={{ width: `${Math.max(4, Math.round(prediction.score * 100))}%` }}
        />
      </div>

      {prediction.contributing_symptoms.length > 0 && (
        <div className="mt-5">
          <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
            Why the model considered this
          </p>
          <ul className="mt-2 flex flex-wrap gap-2">
            {prediction.contributing_symptoms.map((symptom) => (
              <li
                key={symptom}
                className="rounded-full border border-ink-200 px-3 py-1 text-sm dark:border-ink-800"
              >
                {humaniseSymptom(symptom)}
              </li>
            ))}
          </ul>
          <p className="mt-2 text-xs leading-relaxed text-ink-500">
            These are the symptoms you reported that this model weighs most heavily. That is an
            explanation of the model, not evidence that they cause the condition.
          </p>
        </div>
      )}
    </li>
  );
}
