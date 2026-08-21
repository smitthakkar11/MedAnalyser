import type { Safety } from '@/types/assessment';

interface SafetyBannerProps {
  safety: Safety;
}

/**
 * The red-flag warning.
 *
 * Rendered above everything else and styled to dominate the page. This comes
 * from a deterministic rule engine, not the model, and it deliberately does not
 * hedge: telling someone with crushing chest pain that it is "possibly
 * something to look into" would be the single worst thing this product could do.
 *
 * `role="alert"` so it is announced immediately by a screen reader rather than
 * waiting for the user to reach it.
 */
export function SafetyBanner({ safety }: SafetyBannerProps) {
  if (safety.level === 'none') return null;

  const isEmergency = safety.level === 'emergency';

  const shell = isEmergency
    ? 'border-danger-500 bg-danger-500/10 dark:bg-danger-500/15'
    : 'border-amber-400 bg-amber-50 dark:border-amber-700 dark:bg-amber-950/40';
  const badge = isEmergency
    ? 'bg-danger-500 text-white'
    : 'bg-amber-400 text-amber-950';

  return (
    <section
      role="alert"
      aria-labelledby="safety-heading"
      className={`rounded-2xl border-2 p-6 sm:p-8 ${shell}`}
    >
      <span
        className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wider ${badge}`}
      >
        <svg
          viewBox="0 0 24 24"
          className="size-4"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
          <path d="M12 9v4M12 17h.01" />
        </svg>
        {isEmergency ? 'Urgent medical attention' : 'See a doctor today'}
      </span>

      <h2 id="safety-heading" className="mt-4 text-2xl font-bold leading-tight sm:text-3xl">
        {safety.headline}
      </h2>

      <ul className="mt-6 space-y-4">
        {safety.flags.map((flag) => (
          <li key={flag.id} className="border-t border-current/15 pt-4">
            <p className="font-semibold">{flag.title}</p>
            <p className="mt-1 text-sm leading-relaxed">{flag.advice}</p>
            <a
              href={flag.source_url}
              target="_blank"
              rel="noreferrer noopener"
              className="mt-2 inline-block text-xs underline underline-offset-4 opacity-80 hover:opacity-100"
            >
              {flag.source}
            </a>
          </li>
        ))}
      </ul>

      <p className="mt-6 text-sm font-medium">
        This warning comes from a fixed set of rules, not from the AI model, and it takes
        priority over anything else on this page.
      </p>
    </section>
  );
}
