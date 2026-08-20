import type { ComponentStatus } from '@/types/api';

const STATUS_STYLES: Record<ComponentStatus, { dot: string; text: string; label: string }> = {
  ok: {
    dot: 'bg-emerald-500',
    text: 'text-ink-950 dark:text-ink-0',
    label: 'Operational',
  },
  degraded: {
    dot: 'bg-amber-500',
    text: 'text-ink-950 dark:text-ink-0',
    label: 'Degraded',
  },
  unavailable: {
    dot: 'bg-ink-400 dark:bg-ink-600',
    text: 'text-ink-600 dark:text-ink-400',
    label: 'Unavailable',
  },
};

interface StatusBadgeProps {
  status: ComponentStatus;
  label?: string;
}

/** Status chip. Colour is paired with text so it is never the only cue. */
export function StatusBadge({ status, label }: StatusBadgeProps) {
  const style = STATUS_STYLES[status];
  return (
    <span className={`inline-flex items-center gap-2 text-sm font-semibold ${style.text}`}>
      <span className={`size-2 rounded-full ${style.dot}`} aria-hidden="true" />
      {label ?? style.label}
    </span>
  );
}
