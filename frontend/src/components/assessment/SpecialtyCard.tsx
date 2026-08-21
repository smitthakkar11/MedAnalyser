import type { Specialty } from '@/types/assessment';

interface SpecialtyCardProps {
  specialty: Specialty;
}

const BASIS_LABEL: Record<Specialty['basis'], string> = {
  condition: 'Based on the most likely condition',
  symptom: 'Based on your symptoms',
  default: 'No clear direction',
  emergency: 'Overridden by the warning above',
};

/**
 * The suggested specialty.
 *
 * Rendered *below* the safety banner and, when a red flag fired, showing
 * emergency care instead of a referral — pointing someone with crushing chest
 * pain at an outpatient clinic would be the worst thing this could do.
 */
export function SpecialtyCard({ specialty }: SpecialtyCardProps) {
  const isEmergency = specialty.overridden_by_safety;

  return (
    <section aria-labelledby="specialty-heading" className="space-y-4">
      <div className="border-b border-ink-950 pb-4 dark:border-ink-0">
        <h2 id="specialty-heading" className="text-2xl font-bold tracking-tight">
          Who to see
        </h2>
      </div>

      <div
        className={`rounded-2xl border p-6 ${
          isEmergency
            ? 'border-danger-500 bg-danger-500/8'
            : 'border-ink-200 bg-ink-50/60 dark:border-ink-800 dark:bg-ink-900/60'
        }`}
      >
        <p className="text-xs font-semibold uppercase tracking-wider text-ink-500">
          {BASIS_LABEL[specialty.basis]}
        </p>
        <p className="mt-2 text-2xl font-bold tracking-tight">{specialty.display_name}</p>
        {specialty.description && (
          <p className="mt-1 text-sm text-ink-600 dark:text-ink-400">{specialty.description}</p>
        )}
        <p className="mt-4 text-sm leading-relaxed">{specialty.reason}</p>
      </div>

      <p className="text-xs leading-relaxed text-ink-500">
        This is a suggested starting point, not a referral. It comes from a fixed mapping of
        conditions to specialties, not from the AI model. Your own doctor may direct you
        elsewhere, and that judgement takes precedence over this one.
      </p>
    </section>
  );
}
