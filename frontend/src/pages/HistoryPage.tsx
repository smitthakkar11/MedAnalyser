import { Link } from 'react-router-dom';
import { EmptyState } from '@/components/EmptyState';
import { FormAlert } from '@/components/FormAlert';
import { FullPageSpinner } from '@/components/FullPageSpinner';
import { useAsync } from '@/hooks/useAsync';
import { assessmentService } from '@/services/assessmentService';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

export function HistoryPage() {
  const { status, data, error, reload } = useAsync(
    (signal) => assessmentService.list(signal),
    'assessments',
  );

  if (status === 'loading') return <FullPageSpinner label="Loading your history" />;
  if (status === 'error') {
    return (
      <div className="mx-auto max-w-lg space-y-4">
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

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-headline">Your assessments</h1>
          <p className="mt-2 text-ink-600 dark:text-ink-400">
            Everything you have recorded, most recent first.
          </p>
        </div>
        <Link
          to="/assessment/new"
          className="whitespace-nowrap rounded-full bg-gradient-to-r from-accent-blue to-accent-violet px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent-violet/20 transition hover:shadow-xl"
        >
          New assessment
        </Link>
      </header>

      {data.length === 0 ? (
        <EmptyState
          title="No assessments yet"
          body="Describe your symptoms and MedAnalyser will suggest what may be worth discussing with a doctor."
          action={
            <Link to="/assessment/new" className="text-sm font-semibold underline">
              Start your first assessment
            </Link>
          }
        />
      ) : (
        <ol className="border-t border-ink-950 dark:border-ink-0">
          {data.map((assessment) => (
            <li
              key={assessment.id}
              className="border-b border-ink-200 transition-colors hover:bg-ink-50 dark:border-ink-800 dark:hover:bg-ink-900"
            >
              <Link to={`/assessment/${assessment.id}`} className="block py-5">
                <div className="flex flex-wrap items-baseline justify-between gap-3">
                  <span className="font-mono text-xs text-ink-500">
                    {formatDate(assessment.created_at)}
                  </span>
                  {assessment.status === 'completed' ? (
                    <span className="text-xs font-semibold text-ink-600 dark:text-ink-400">
                      {assessment.symptom_count} symptom
                      {assessment.symptom_count === 1 ? '' : 's'}
                    </span>
                  ) : (
                    <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-900 dark:bg-amber-950/50 dark:text-amber-200">
                      Not finished
                    </span>
                  )}
                </div>
                <p className="mt-1 text-lg font-semibold">
                  {assessment.top_condition ?? 'No result recorded'}
                </p>
                <p className="mt-0.5 truncate text-sm text-ink-600 dark:text-ink-400">
                  {assessment.input_text}
                </p>
              </Link>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}
