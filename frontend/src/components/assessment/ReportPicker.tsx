import { useEffect, useState } from 'react';
import { reportService } from '@/services/reportService';
import type { LinkedReport } from '@/types/assessment';
import type { ReportSummary } from '@/types/report';

interface ReportPickerProps {
  linked: LinkedReport[];
  onAttach: (reportId: string) => void;
  onDetach: (reportId: string) => void;
  pending: boolean;
}

/**
 * Choose which uploaded reports this assessment should consider.
 *
 * The copy is deliberate about what attaching does: the values are shown and
 * they steer the questions, but they are not fed to the model.
 */
export function ReportPicker({ linked, onAttach, onDetach, pending }: ReportPickerProps) {
  const [available, setAvailable] = useState<ReportSummary[] | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    reportService
      .list(controller.signal)
      .then((reports) => setAvailable(reports.filter((r) => r.status === 'processed')))
      .catch(() => setAvailable([]));
    return () => controller.abort();
  }, []);

  if (available === null) return null;
  if (available.length === 0 && linked.length === 0) return null;

  const linkedIds = new Set(linked.map((report) => report.id));

  return (
    <section
      aria-labelledby="attach-reports-heading"
      className="rounded-2xl border border-ink-200 bg-ink-50/60 p-5 dark:border-ink-800 dark:bg-ink-900/60"
    >
      <h2 id="attach-reports-heading" className="text-sm font-semibold">
        Include a lab report?
      </h2>
      <p className="mt-1 text-xs leading-relaxed text-ink-600 dark:text-ink-400">
        Its values will be shown with your result and may prompt extra questions. They are not
        fed into the model, which works from your symptoms alone.
      </p>

      <ul className="mt-4 space-y-2">
        {available.map((report) => {
          const isLinked = linkedIds.has(report.id);
          return (
            <li key={report.id} className="flex items-center justify-between gap-4">
              <span className="min-w-0 flex-1 truncate text-sm">
                {report.original_filename}
                <span className="ml-2 text-xs text-ink-500">
                  {report.value_count} value{report.value_count === 1 ? '' : 's'}
                  {report.abnormal_count > 0 && ` · ${report.abnormal_count} out of range`}
                </span>
              </span>
              <button
                type="button"
                disabled={pending}
                onClick={() => (isLinked ? onDetach(report.id) : onAttach(report.id))}
                className={`shrink-0 rounded-full border px-4 py-1.5 text-xs font-semibold transition disabled:opacity-50 ${
                  isLinked
                    ? 'border-accent-blue bg-accent-blue/12'
                    : 'border-ink-300 hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0'
                }`}
              >
                {isLinked ? 'Included' : 'Include'}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
