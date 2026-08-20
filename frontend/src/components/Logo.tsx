interface LogoProps {
  className?: string;
}

/** MedAnalyser wordmark with an inline SVG mark (no external asset). */
export function Logo({ className = '' }: LogoProps) {
  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <svg
        viewBox="0 0 24 24"
        className="size-6 text-ink-950 dark:text-ink-0"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <rect x="2.5" y="4.5" width="19" height="15" rx="3" />
        <path d="M6 12h3l1.5-3 2.5 6 1.5-3H18" />
      </svg>
      <span className="text-[19px] font-bold tracking-tight text-ink-950 dark:text-ink-0">
        MedAnalyser
      </span>
    </span>
  );
}
