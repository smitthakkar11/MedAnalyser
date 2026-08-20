interface StepProgressProps {
  /** Zero-based index of the current step. */
  current: number;
  total: number;
  label: string;
}

/** Progress indicator for a multi-step flow. */
export function StepProgress({ current, total, label }: StepProgressProps) {
  const percent = Math.round(((current + 1) / total) * 100);

  return (
    <div className="space-y-3">
      <div className="flex items-baseline justify-between gap-4">
        <p className="text-sm font-semibold text-accent-violet">
          Step {current + 1} of {total}
        </p>
        <p className="text-xs text-ink-500">{label}</p>
      </div>
      <div
        className="h-1 overflow-hidden rounded-full bg-ink-200 dark:bg-ink-800"
        role="progressbar"
        aria-valuenow={percent}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Onboarding progress"
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent-teal via-accent-blue to-accent-violet transition-[width] duration-500"
          style={{ width: `${percent}%` }}
        />
      </div>
    </div>
  );
}
