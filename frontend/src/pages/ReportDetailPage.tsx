import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { FormAlert } from '@/components/FormAlert';
import { FullPageSpinner } from '@/components/FullPageSpinner';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { ValueTable } from '@/components/reports/ValueTable';
import { useAsync } from '@/hooks/useAsync';
import { ApiError } from '@/services/apiClient';
import { reportService } from '@/services/reportService';
import { EXTRACTION_METHOD_LABEL, formatFileSize } from '@/types/report';

export function ReportDetailPage() {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const { status, data, error } = useAsync(
    (signal) => reportService.get(id, signal),
    `report:${id}`,
  );
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [downloading, setDownloading] = useState(false);

  async function remove() {
    setDeleteError(null);
    setDeleting(true);
    try {
      await reportService.remove(id);
      navigate('/reports', { replace: true });
    } catch (caught) {
      setDeleteError(
        caught instanceof ApiError ? caught.message : 'Could not delete this report.',
      );
      setDeleting(false);
    }
  }

  async function download() {
    if (status !== 'success') return;
    setDeleteError(null);
    setDownloading(true);
    try {
      await reportService.download(id, data.original_filename);
    } catch (caught) {
      setDeleteError(
        caught instanceof ApiError ? caught.message : 'Could not download this report.',
      );
    } finally {
      setDownloading(false);
    }
  }

  if (status === 'loading') return <FullPageSpinner label="Loading report" />;
  if (status === 'error') {
    return (
      <div className="mx-auto max-w-lg space-y-4">
        <FormAlert message={error.message} />
        <Link to="/reports" className="text-sm font-semibold underline">
          Back to reports
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-10">
      <header>
        <p className="text-sm text-ink-500">
          {data.report_date
            ? `Report date ${data.report_date}`
            : `Uploaded ${new Date(data.created_at).toLocaleDateString()}`}
        </p>
        <h1 className="mt-2 break-words text-headline">{data.original_filename}</h1>
        <p className="mt-3 text-sm text-ink-600 dark:text-ink-400">
          {formatFileSize(data.size_bytes)}
          {data.page_count ? ` · ${data.page_count} page${data.page_count === 1 ? '' : 's'}` : ''}
          {data.extraction_method
            ? ` · ${EXTRACTION_METHOD_LABEL[data.extraction_method]}`
            : ''}
        </p>
      </header>

      {data.extraction_method === 'ocr' && (
        <div
          role="note"
          className="rounded-xl border border-amber-200 bg-amber-50/70 px-5 py-4 text-sm leading-relaxed text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-200"
        >
          This report had no text layer, so the values below were read from the image by OCR.
          That is less reliable than a digital report — please check them against the original.
        </div>
      )}

      {data.error_message && (
        <div className="rounded-xl border border-ink-200 bg-ink-50/60 px-5 py-4 text-sm dark:border-ink-800 dark:bg-ink-900/60">
          {data.error_message}
        </div>
      )}

      <section aria-labelledby="values-heading" className="space-y-4">
        <h2 id="values-heading" className="text-2xl font-bold tracking-tight">
          Extracted values
        </h2>
        <p className="text-sm leading-relaxed text-ink-600 dark:text-ink-400">
          These are read from the document itself. Where a reading says{' '}
          <em>no range given</em>, the report printed none — MedAnalyser does not supply
          reference ranges of its own, because they vary by laboratory and assay.
        </p>
        <ValueTable values={data.values} />
      </section>

      {deleteError && <FormAlert message={deleteError} />}

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          disabled={downloading}
          onClick={() => void download()}
          className="rounded-full border border-ink-300 px-5 py-2.5 text-sm font-semibold transition hover:border-ink-950 disabled:opacity-50 dark:border-ink-700 dark:hover:border-ink-0"
        >
          {downloading ? 'Preparing…' : 'Download original'}
        </button>
        <Link
          to="/reports"
          className="rounded-full border border-ink-300 px-5 py-2.5 text-sm font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
        >
          Back to reports
        </Link>
        <button
          type="button"
          disabled={deleting}
          onClick={() => void remove()}
          className="rounded-full px-5 py-2.5 text-sm font-semibold text-danger-600 transition hover:underline disabled:opacity-50 dark:text-danger-400"
        >
          {deleting ? 'Deleting…' : 'Delete report'}
        </button>
      </div>

      <MedicalDisclaimer />
    </div>
  );
}
