import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { useAuth } from '@/hooks/useAuth';

/**
 * Signed-in landing screen.
 *
 * Phase 2 establishes the authenticated shell; the real dashboard — recent
 * assessments, reports, medical timeline and health trends — is Phase 3.
 */
export function DashboardPage() {
  const { user } = useAuth();
  const firstName = user?.name.split(' ')[0] ?? 'there';

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-headline">Welcome, {firstName}</h1>
        <p className="mt-3 max-w-xl text-lg text-ink-600 dark:text-ink-400">
          Your account is set up and age-verified. Assessments and report uploads arrive in the
          next phase.
        </p>
      </div>

      <dl className="grid gap-px overflow-hidden rounded-2xl border border-ink-200 bg-ink-200 sm:grid-cols-3 dark:border-ink-800 dark:bg-ink-800">
        <div className="bg-ink-0 p-6 dark:bg-ink-950">
          <dt className="text-sm text-ink-600 dark:text-ink-400">Signed in as</dt>
          <dd className="mt-1 truncate text-lg font-semibold">{user?.email}</dd>
        </div>
        <div className="bg-ink-0 p-6 dark:bg-ink-950">
          <dt className="text-sm text-ink-600 dark:text-ink-400">Date of birth</dt>
          <dd className="mt-1 text-lg font-semibold">{user?.date_of_birth ?? '—'}</dd>
        </div>
        <div className="bg-ink-0 p-6 dark:bg-ink-950">
          <dt className="text-sm text-ink-600 dark:text-ink-400">Sign-in methods</dt>
          <dd className="mt-1 text-lg font-semibold capitalize">
            {[user?.has_password ? 'password' : null, ...(user?.linked_providers ?? [])]
              .filter(Boolean)
              .join(', ') || '—'}
          </dd>
        </div>
      </dl>

      <section
        aria-labelledby="next-heading"
        className="rounded-2xl border border-dashed border-ink-300 p-10 text-center dark:border-ink-700"
      >
        <h2 id="next-heading" className="text-xl font-bold">
          No assessments yet
        </h2>
        <p className="mx-auto mt-2 max-w-md text-ink-600 dark:text-ink-400">
          Once symptom assessment and report upload are available, everything you record will
          appear here as a medical timeline.
        </p>
      </section>

      <MedicalDisclaimer />
    </div>
  );
}
