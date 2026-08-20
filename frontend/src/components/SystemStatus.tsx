import { healthService } from '@/services/healthService';
import { useAsync } from '@/hooks/useAsync';
import { StatusBadge } from '@/components/StatusBadge';

/**
 * Live backend connectivity panel.
 *
 * This is the end-to-end proof that the browser, the dev/nginx proxy, the
 * FastAPI app and (when running) PostgreSQL are wired together.
 */
export function SystemStatus() {
  const { status, data, error, reload } = useAsync(
    (signal) => healthService.getReadiness(signal),
    'health:readiness',
  );

  return (
    <section id="system-status" aria-labelledby="system-status-heading" className="scroll-mt-24">
      <div className="flex flex-wrap items-end justify-between gap-4 border-b border-ink-950 pb-5 dark:border-ink-0">
        <div>
          <h2
            id="system-status-heading"
            className="text-3xl font-bold tracking-tight sm:text-4xl"
          >
            System status
          </h2>
          <p className="mt-2 text-sm text-ink-600 dark:text-ink-400">
            Live connectivity between this app and the MedAnalyser API.
          </p>
        </div>
        <button
          type="button"
          onClick={reload}
          className="rounded-full border border-ink-300 px-5 py-2 text-sm font-semibold transition hover:border-ink-950 hover:bg-ink-950 hover:text-ink-0 dark:border-ink-700 dark:hover:border-ink-0 dark:hover:bg-ink-0 dark:hover:text-ink-950"
        >
          Refresh
        </button>
      </div>

      <div className="mt-8">
        {status === 'loading' && (
          <div className="space-y-4" aria-live="polite" aria-busy="true">
            <div className="h-6 w-48 animate-pulse rounded bg-ink-100 dark:bg-ink-800" />
            <div className="h-6 w-64 animate-pulse rounded bg-ink-100 dark:bg-ink-850" />
            <span className="sr-only">Checking service status…</span>
          </div>
        )}

        {status === 'error' && (
          <div
            role="alert"
            className="border border-ink-200 bg-ink-50 p-6 dark:border-ink-800 dark:bg-ink-900"
          >
            <p className="text-lg font-bold">API unreachable</p>
            <p className="mt-1 text-sm text-ink-600 dark:text-ink-400">{error.message}</p>
            <p className="mt-4 text-xs text-ink-500">
              Start the backend with{' '}
              <code className="rounded bg-ink-200 px-1.5 py-0.5 font-mono text-ink-950 dark:bg-ink-800 dark:text-ink-0">
                uvicorn app.main:app --reload
              </code>{' '}
              from the <code className="font-mono">backend/</code> directory.
            </p>
          </div>
        )}

        {status === 'success' && (
          <dl className="divide-y divide-ink-200 dark:divide-ink-800">
            <div className="flex items-center justify-between gap-6 py-5">
              <dt className="flex items-baseline gap-3">
                <span className="text-lg font-semibold">API</span>
                <span className="font-mono text-xs text-ink-500">v{data.version}</span>
              </dt>
              <dd>
                <StatusBadge status="ok" label="Connected" />
              </dd>
            </div>

            {data.dependencies.map((dependency) => (
              <div
                key={dependency.name}
                className="flex items-start justify-between gap-6 py-5"
              >
                <dt>
                  <span className="text-lg font-semibold capitalize">{dependency.name}</span>
                  {dependency.detail && (
                    <span className="mt-1 block max-w-md text-sm text-ink-600 dark:text-ink-400">
                      {dependency.detail}
                    </span>
                  )}
                </dt>
                <dd className="shrink-0 pt-1">
                  <StatusBadge status={dependency.status} />
                </dd>
              </div>
            ))}
          </dl>
        )}
      </div>
    </section>
  );
}
