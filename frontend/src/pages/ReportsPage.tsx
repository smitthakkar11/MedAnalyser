import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { EmptyState } from '@/components/EmptyState';
import { FormAlert } from '@/components/FormAlert';
import { FullPageSpinner } from '@/components/FullPageSpinner';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { UploadDropzone } from '@/components/reports/UploadDropzone';
import { useAsync } from '@/hooks/useAsync';
import { ApiError } from '@/services/apiClient';
import { reportService } from '@/services/reportService';
import { formatFileSize } from '@/types/report';

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}

export function ReportsPage() {
  const navigate = useNavigate();
  const { status, data, error, reload } = useAsync(
    (signal) => reportService.list(signal),
    'reports',
  );
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function upload(file: File) {
    setUploadError(null);
    setPending(true);
    try {
      const report = await reportService.upload(file);
      navigate(`/reports/${report.id}`);
    } catch (caught) {
      if (caught instanceof ApiError) {
        const existing = caught.details['existing_report_id'];
        if (typeof existing === 'string') {
          navigate(`/reports/${existing}`);
          return;
        }
        setUploadError(caught.message);
      } else {
        setUploadError('Could not upload that file.');
      }
    } finally {
      setPending(false);
      reload();
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <header>
        <h1 className="text-headline">Medical reports</h1>
        <p className="mt-3 text-lg text-ink-600 dark:text-ink-400">
          Upload a lab report and MedAnalyser will read the values off it. Everything shown is
          taken from the document — nothing is estimated or filled in.
        </p>
      </header>

      {uploadError && <FormAlert message={uploadError} />}

      <UploadDropzone onFile={(file) => void upload(file)} pending={pending} />

      <section aria-labelledby="uploaded-heading" className="space-y-5">
        <h2 id="uploaded-heading" className="text-2xl font-bold tracking-tight">
          Your reports
        </h2>

        {status === 'loading' && <FullPageSpinner label="Loading your reports" />}

        {status === 'error' && (
          <div className="space-y-3">
            <FormAlert message={error.message} />
            <button
              type="button"
              onClick={reload}
              className="rounded-full border border-ink-300 px-5 py-2.5 text-sm font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
            >
              Try again
            </button>
          </div>
        )}

        {status === 'success' &&
          (data.length === 0 ? (
            <EmptyState
              title="No reports yet"
              body="Upload a PDF lab report to have its values extracted and kept alongside your assessments."
            />
          ) : (
            <ol className="border-t border-ink-950 dark:border-ink-0">
              {data.map((report) => (
                <li
                  key={report.id}
                  className="border-b border-ink-200 transition-colors hover:bg-ink-50 dark:border-ink-800 dark:hover:bg-ink-900"
                >
                  <Link to={`/reports/${report.id}`} className="block py-5">
                    <div className="flex flex-wrap items-baseline justify-between gap-3">
                      <span className="font-mono text-xs text-ink-500">
                        {report.report_date ?? formatDate(report.created_at)}
                      </span>
                      {report.status === 'failed' ? (
                        <span className="rounded-full bg-amber-100 px-2.5 py-1 text-xs font-semibold text-amber-900 dark:bg-amber-950/50 dark:text-amber-200">
                          Could not read
                        </span>
                      ) : (
                        <span className="text-xs text-ink-600 dark:text-ink-400">
                          {report.value_count} value{report.value_count === 1 ? '' : 's'}
                          {report.abnormal_count > 0 &&
                            ` · ${report.abnormal_count} outside range`}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 truncate text-lg font-semibold">
                      {report.original_filename}
                    </p>
                    <p className="mt-0.5 text-sm text-ink-600 dark:text-ink-400">
                      {formatFileSize(report.size_bytes)}
                      {report.page_count ? ` · ${report.page_count} page${report.page_count === 1 ? '' : 's'}` : ''}
                    </p>
                  </Link>
                </li>
              ))}
            </ol>
          ))}
      </section>

      <MedicalDisclaimer />
    </div>
  );
}
