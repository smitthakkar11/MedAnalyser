import type { LabFinding } from '@/types/assessment';

const FLAG_STYLE: Record<LabFinding['flag'], string> = {
  low: 'bg-accent-blue/12 text-accent-blue',
  high: 'bg-danger-500/12 text-danger-600 dark:text-danger-400',
  normal: 'bg-accent-teal/12 text-accent-teal',
  unknown: 'bg-ink-100 text-ink-600 dark:bg-ink-800 dark:text-ink-400',
};

const FLAG_LABEL: Record<LabFinding['flag'], string> = {
  low: 'Below range',
  high: 'Above range',
  normal: 'In range',
  unknown: 'No range given',
};

interface LabFindingsProps {
  findings: LabFinding[];
}

/**
 * Laboratory values from reports attached to an assessment.
 *
 * Rendered as a section of its own, deliberately apart from the predictions.
 * These numbers were **read from a document**; the predictions were **produced
 * by a model** that has never seen a laboratory value. Blending the two into
 * one list would imply the model weighed them.
 */
export function LabFindings({ findings }: LabFindingsProps) {
  if (findings.length === 0) return null;

  const abnormal = findings.filter((finding) => finding.flag === 'low' || finding.flag === 'high');

  return (
    <section aria-labelledby="lab-findings-heading" className="space-y-4">
      <div className="border-b border-ink-950 pb-4 dark:border-ink-0">
        <h2 id="lab-findings-heading" className="text-2xl font-bold tracking-tight">
          From your reports
        </h2>
        <p className="mt-2 text-sm leading-relaxed text-ink-600 dark:text-ink-400">
          Read directly from the documents you uploaded — <strong>not</strong> produced by the
          model, which works from your symptoms alone. Anything marked out of range is out of
          range according to that report&rsquo;s own printed reference values.
        </p>
      </div>

      {abnormal.length > 0 && (
        <p className="text-sm font-medium">
          {abnormal.length} of {findings.length} value{findings.length === 1 ? '' : 's'} fell
          outside the range printed on the report.
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] text-left text-sm">
          <thead>
            <tr className="border-b border-ink-200 dark:border-ink-800">
              <th scope="col" className="pb-3 pr-4 font-semibold">Test</th>
              <th scope="col" className="pb-3 pr-4 font-semibold">Result</th>
              <th scope="col" className="pb-3 pr-4 font-semibold">Range on report</th>
              <th scope="col" className="pb-3 font-semibold">Reading</th>
            </tr>
          </thead>
          <tbody>
            {findings.map((finding) => (
              <tr
                key={`${finding.report_id}-${finding.analyte}`}
                className="border-b border-ink-200 dark:border-ink-800"
              >
                <th scope="row" className="py-3 pr-4 font-medium">
                  {finding.display_name}
                </th>
                <td className="py-3 pr-4 font-mono">
                  {finding.value.toLocaleString()}
                  {finding.unit ? ` ${finding.unit}` : ''}
                </td>
                <td className="py-3 pr-4 font-mono text-ink-600 dark:text-ink-400">
                  {finding.reference_text ?? '—'}
                </td>
                <td className="py-3">
                  <span
                    className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${FLAG_STYLE[finding.flag]}`}
                  >
                    {FLAG_LABEL[finding.flag]}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
