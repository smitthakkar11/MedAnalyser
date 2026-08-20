import { formatValue, type ReportValue, type ValueFlag } from '@/types/report';

const FLAG_STYLE: Record<ValueFlag, string> = {
  low: 'bg-accent-blue/12 text-accent-blue',
  high: 'bg-danger-500/12 text-danger-600 dark:text-danger-400',
  normal: 'bg-accent-teal/12 text-accent-teal',
  unknown: 'bg-ink-100 text-ink-600 dark:bg-ink-800 dark:text-ink-400',
};

const FLAG_LABEL: Record<ValueFlag, string> = {
  low: 'Below range',
  high: 'Above range',
  normal: 'In range',
  unknown: 'No range given',
};

interface ValueTableProps {
  values: ReportValue[];
}

/**
 * Laboratory values read off a report.
 *
 * Every flag comes from a range printed on that report. Where the document
 * gave no range the value is shown without judgement — MedAnalyser supplies no
 * normal ranges of its own, because they vary by laboratory and assay.
 */
export function ValueTable({ values }: ValueTableProps) {
  if (values.length === 0) {
    return (
      <p className="rounded-xl border border-dashed border-ink-300 px-6 py-8 text-center text-sm text-ink-500 dark:border-ink-700">
        No laboratory values were recognised in this report.
      </p>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] text-left text-sm">
        <thead>
          <tr className="border-b border-ink-950 dark:border-ink-0">
            <th scope="col" className="pb-3 pr-4 font-semibold">Test</th>
            <th scope="col" className="pb-3 pr-4 font-semibold">Result</th>
            <th scope="col" className="pb-3 pr-4 font-semibold">Range on report</th>
            <th scope="col" className="pb-3 font-semibold">Reading</th>
          </tr>
        </thead>
        <tbody>
          {values.map((value) => (
            <tr key={value.id} className="border-b border-ink-200 dark:border-ink-800">
              <th scope="row" className="py-3 pr-4 font-medium">
                {value.display_name}
              </th>
              <td className="py-3 pr-4 font-mono">
                {formatValue(value)}
                {value.unit_unrecognised && (
                  <span
                    title="This unit was not recognised, so the value is shown exactly as printed and is not comparable across reports."
                    className="ml-2 cursor-help text-xs text-amber-600 dark:text-amber-400"
                  >
                    unit?
                  </span>
                )}
              </td>
              <td className="py-3 pr-4 font-mono text-ink-600 dark:text-ink-400">
                {value.reference_text ?? '—'}
              </td>
              <td className="py-3">
                <span
                  className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${FLAG_STYLE[value.flag]}`}
                >
                  {FLAG_LABEL[value.flag]}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
