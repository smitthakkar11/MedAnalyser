import type { ReactNode } from 'react';

interface EmptyStateProps {
  title: string;
  body: string;
  action?: ReactNode;
}

/** Placeholder for a section that has no data yet. */
export function EmptyState({ title, body, action }: EmptyStateProps) {
  return (
    <div className="rounded-2xl border border-dashed border-ink-300 px-6 py-10 text-center dark:border-ink-700">
      <p className="font-semibold">{title}</p>
      <p className="mx-auto mt-1.5 max-w-sm text-sm leading-relaxed text-ink-600 dark:text-ink-400">
        {body}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}
