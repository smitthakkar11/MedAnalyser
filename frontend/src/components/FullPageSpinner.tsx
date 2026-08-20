interface FullPageSpinnerProps {
  label?: string;
}

/** Centred loading state for route-level waits. */
export function FullPageSpinner({ label = 'Loading' }: FullPageSpinnerProps) {
  return (
    <div
      className="flex min-h-[60vh] flex-col items-center justify-center gap-4"
      role="status"
      aria-live="polite"
    >
      <span className="size-8 animate-spin rounded-full border-2 border-ink-200 border-t-ink-950 dark:border-ink-800 dark:border-t-ink-0" />
      <span className="text-sm text-ink-500">{label}…</span>
    </div>
  );
}
