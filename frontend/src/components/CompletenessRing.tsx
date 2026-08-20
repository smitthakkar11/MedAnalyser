interface CompletenessRingProps {
  /** 0–100. */
  value: number;
}

/** A small progress ring for profile completeness. */
export function CompletenessRing({ value }: CompletenessRingProps) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, value));
  const offset = circumference * (1 - clamped / 100);

  return (
    <div className="relative size-16 shrink-0">
      <svg viewBox="0 0 64 64" className="size-16 -rotate-90" aria-hidden="true">
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="6"
          className="stroke-ink-200 dark:stroke-ink-800"
        />
        <defs>
          <linearGradient id="completeness-ring" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="var(--color-accent-teal)" />
            <stop offset="100%" stopColor="var(--color-accent-blue)" />
          </linearGradient>
        </defs>
        <circle
          cx="32"
          cy="32"
          r={radius}
          fill="none"
          strokeWidth="6"
          strokeLinecap="round"
          stroke="url(#completeness-ring)"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          className="transition-[stroke-dashoffset] duration-700"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center text-sm font-bold">
        {clamped}%
      </span>
      <span className="sr-only">{clamped}% of your profile is complete</span>
    </div>
  );
}
