import { Link } from 'react-router-dom';
import { CompletenessRing } from '@/components/CompletenessRing';
import { EmptyState } from '@/components/EmptyState';
import { FormAlert } from '@/components/FormAlert';
import { FullPageSpinner } from '@/components/FullPageSpinner';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { useAsync } from '@/hooks/useAsync';
import { profileService } from '@/services/profileService';

interface StatProps {
  label: string;
  value: number | string;
}

function Stat({ label, value }: StatProps) {
  return (
    <div className="bg-ink-0 p-6 dark:bg-ink-950">
      <dt className="text-sm text-ink-600 dark:text-ink-400">{label}</dt>
      <dd className="mt-1 text-3xl font-bold tracking-tight">{value}</dd>
    </div>
  );
}

export function DashboardPage() {
  const { status, data, error, reload } = useAsync(
    (signal) => profileService.getDashboard(signal),
    'dashboard',
  );

  if (status === 'loading') return <FullPageSpinner label="Loading your dashboard" />;

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

  const { profile } = data;
  const firstName = data.user_name.split(' ')[0] ?? 'there';
  const profileIncomplete = profile.completeness < 100;

  return (
    <div className="space-y-12">
      <header>
        <h1 className="text-headline">Welcome, {firstName}</h1>
        <p className="mt-3 max-w-xl text-lg text-ink-600 dark:text-ink-400">
          Here is what MedAnalyser knows about you so far.
        </p>
      </header>

      {profileIncomplete && (
        <section
          aria-labelledby="complete-profile-heading"
          className="flex flex-wrap items-center gap-6 rounded-2xl border border-ink-200 bg-ink-50/60 p-6 dark:border-ink-800 dark:bg-ink-900/60"
        >
          <CompletenessRing value={profile.completeness} />
          <div className="min-w-60 flex-1">
            <h2 id="complete-profile-heading" className="font-bold">
              Complete your medical profile
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-600 dark:text-ink-400">
              Allergies, existing conditions and current medications all change how your
              symptoms should be read. Adding them makes every future assessment sharper.
            </p>
          </div>
          <Link
            to="/profile"
            className="whitespace-nowrap rounded-full bg-gradient-to-r from-accent-blue to-accent-violet px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent-violet/20 transition hover:shadow-xl hover:shadow-accent-violet/35"
          >
            Complete profile
          </Link>
        </section>
      )}

      <section aria-labelledby="at-a-glance-heading">
        <h2 id="at-a-glance-heading" className="sr-only">
          Your details at a glance
        </h2>
        <dl className="grid gap-px overflow-hidden rounded-2xl border border-ink-200 bg-ink-200 sm:grid-cols-2 lg:grid-cols-4 dark:border-ink-800 dark:bg-ink-800">
          <Stat label="Age" value={profile.age ?? '—'} />
          <Stat label="Allergies" value={profile.allergy_count} />
          <Stat label="Conditions" value={profile.condition_count} />
          <Stat label="Current medications" value={profile.current_medication_count} />
        </dl>
      </section>

      <section aria-labelledby="assessments-heading" className="space-y-5">
        <div className="flex items-end justify-between gap-4 border-b border-ink-950 pb-4 dark:border-ink-0">
          <h2 id="assessments-heading" className="text-2xl font-bold tracking-tight">
            Recent assessments
          </h2>
          <span className="text-sm text-ink-500">{data.assessment_count} saved</span>
        </div>
        <EmptyState
          title="No assessments yet"
          body="Describing your symptoms and starting an assessment becomes available in the next phase of the build."
        />
      </section>

      <section aria-labelledby="reports-heading" className="space-y-5">
        <div className="flex items-end justify-between gap-4 border-b border-ink-950 pb-4 dark:border-ink-0">
          <h2 id="reports-heading" className="text-2xl font-bold tracking-tight">
            Recent reports
          </h2>
          <span className="text-sm text-ink-500">{data.report_count} uploaded</span>
        </div>
        <EmptyState
          title="No reports yet"
          body="Uploading a PDF lab report, and having its values extracted automatically, arrives with medical report processing."
        />
      </section>

      <MedicalDisclaimer />
    </div>
  );
}
