import type { Knowledge } from '@/types/assessment';

interface TreatmentInfoProps {
  knowledge: Knowledge;
}

/**
 * Treatment and medication information for the top predicted condition.
 *
 * Describes classes of medicine and what to discuss with a doctor. It states
 * no doses and never tells anyone to start, stop or change a medicine — the
 * backend enforces both, and the disclaimer is rendered unconditionally.
 *
 * Where the user's own profile records a related allergy, that entry is
 * flagged rather than shown flat.
 */
export function TreatmentInfo({ knowledge }: TreatmentInfoProps) {
  return (
    <section aria-labelledby="treatment-heading" className="space-y-6">
      <div className="border-b border-ink-950 pb-4 dark:border-ink-0">
        <h2 id="treatment-heading" className="text-2xl font-bold tracking-tight">
          About {knowledge.condition}
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-600 dark:text-ink-400">
          General information to help you have a better-informed conversation. It is not
          advice about your case and not a prescription.
        </p>
      </div>

      {knowledge.summary && (
        <div>
          <p className="leading-relaxed">{knowledge.summary}</p>
          {knowledge.summary_source && (
            <p className="mt-2 text-xs text-ink-500">
              Source:{' '}
              {knowledge.summary_source_url ? (
                <a
                  href={knowledge.summary_source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="underline underline-offset-4"
                >
                  {knowledge.summary_source}
                </a>
              ) : (
                knowledge.summary_source
              )}
            </p>
          )}
        </div>
      )}

      {knowledge.approaches.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-ink-500">
            How this is usually approached
          </h3>
          <ul className="mt-3 space-y-2">
            {knowledge.approaches.map((approach) => (
              <li key={approach} className="flex gap-3 text-sm leading-relaxed">
                <span aria-hidden="true" className="text-accent-teal">
                  •
                </span>
                {approach}
              </li>
            ))}
          </ul>
        </div>
      )}

      {knowledge.medications.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-ink-500">
            Medicines that may come up
          </h3>
          <ul className="mt-3 space-y-3">
            {knowledge.medications.map((medicine) => (
              <li
                key={medicine.key}
                className={`rounded-xl border p-4 ${
                  medicine.allergy_warning
                    ? 'border-danger-500/50 bg-danger-500/8'
                    : 'border-ink-200 dark:border-ink-800'
                }`}
              >
                <p className="font-semibold">{medicine.display_name}</p>
                <p className="mt-1 text-sm leading-relaxed">{medicine.common_uses}</p>
                <p className="mt-2 text-sm leading-relaxed text-ink-600 dark:text-ink-400">
                  {medicine.considerations}
                </p>

                {medicine.allergy_warning && (
                  <p
                    role="alert"
                    className="mt-3 rounded-lg bg-danger-500/12 px-3 py-2 text-sm font-medium"
                  >
                    {medicine.allergy_warning}
                  </p>
                )}

                <a
                  href={medicine.source_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="mt-2 inline-block text-xs text-ink-500 underline underline-offset-4"
                >
                  {medicine.source}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {knowledge.questions.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold uppercase tracking-wider text-ink-500">
            Worth asking your doctor
          </h3>
          <ul className="mt-3 space-y-2">
            {knowledge.questions.map((question) => (
              <li
                key={question}
                className="rounded-xl border border-ink-200 px-4 py-3 text-sm dark:border-ink-800"
              >
                {question}
              </li>
            ))}
          </ul>
        </div>
      )}

      <p className="rounded-xl border border-amber-200 bg-amber-50/70 px-5 py-4 text-sm font-medium leading-relaxed text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200">
        {knowledge.disclaimer}
      </p>
    </section>
  );
}
