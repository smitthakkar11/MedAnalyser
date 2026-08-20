interface LabRow {
  name: string;
  value: string;
  /** Bar fill as a percentage of the reference range. */
  fill: number;
  tone: 'low' | 'high' | 'normal';
}

/** Illustrative values only — not derived from any real report. */
const LAB_ROWS: readonly LabRow[] = [
  { name: 'Hemoglobin', value: '10.8 g/dL', fill: 42, tone: 'low' },
  { name: 'WBC', value: '13,500 /μL', fill: 88, tone: 'high' },
  { name: 'Platelets', value: '180,000 /μL', fill: 64, tone: 'normal' },
  { name: 'Ferritin', value: '14 ng/mL', fill: 24, tone: 'low' },
] as const;

const TONE_BAR: Record<LabRow['tone'], string> = {
  low: 'bg-gradient-to-r from-accent-amber to-accent-magenta',
  high: 'bg-gradient-to-r from-accent-violet to-accent-blue',
  normal: 'bg-gradient-to-r from-accent-teal to-accent-lime',
};

const TONE_TEXT: Record<LabRow['tone'], string> = {
  low: 'text-accent-magenta',
  high: 'text-accent-violet',
  normal: 'text-accent-teal',
};

/**
 * Animated hero graphic: a medical report being read, values extracted, and a
 * specialty suggested.
 *
 * Built entirely from markup and CSS — no image or video files, so it is sharp
 * at any size, themes correctly, adds nothing to the bundle, and honours
 * `prefers-reduced-motion` (the global rule collapses the animations).
 *
 * Purely decorative: hidden from assistive technology, and every value shown is
 * illustrative.
 */
export function HeroVisual() {
  return (
    <div aria-hidden="true" className="relative isolate mx-auto w-full max-w-lg select-none">
      {/* Colour wash */}
      <div className="pointer-events-none absolute inset-0 -z-10">
        <div className="animate-float-slow absolute -left-10 top-4 size-56 rounded-full bg-accent-violet/30 blur-3xl dark:bg-accent-violet/25" />
        <div className="animate-drift absolute -right-8 top-24 size-64 rounded-full bg-accent-teal/30 blur-3xl dark:bg-accent-teal/20" />
        <div className="animate-float-slow absolute bottom-0 left-16 size-48 rounded-full bg-accent-amber/25 blur-3xl dark:bg-accent-amber/15" />
      </div>

      {/* Report card */}
      <div className="animate-rise-in relative overflow-hidden rounded-2xl border border-ink-200 bg-ink-0/80 p-6 shadow-2xl shadow-ink-950/10 backdrop-blur-xl dark:border-ink-800 dark:bg-ink-900/80 dark:shadow-black/50">
        {/* Scanning highlight */}
        <div className="animate-scan pointer-events-none absolute inset-x-0 top-0 h-20 bg-gradient-to-b from-transparent via-accent-teal/20 to-transparent" />

        <div className="flex items-center justify-between gap-4 border-b border-ink-200 pb-4 dark:border-ink-800">
          <div className="flex items-center gap-2.5">
            <span className="inline-flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-accent-blue to-accent-violet text-white">
              <svg
                viewBox="0 0 24 24"
                className="size-4"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z" />
                <path d="M14 2v6h6" />
              </svg>
            </span>
            <span className="font-mono text-xs text-ink-600 dark:text-ink-400">
              CBC_report.pdf
            </span>
          </div>

          <span className="inline-flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-ink-600 dark:text-ink-400">
            <span className="relative flex size-2">
              <span className="animate-pulse-ring absolute inline-flex size-full rounded-full bg-accent-lime" />
              <span className="relative inline-flex size-2 rounded-full bg-accent-lime" />
            </span>
            Analysing
          </span>
        </div>

        {/* Extracted values */}
        <ul className="mt-5 space-y-4">
          {LAB_ROWS.map((row, index) => (
            <li key={row.name}>
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-medium text-ink-700 dark:text-ink-300">
                  {row.name}
                </span>
                <span className={`font-mono text-sm font-semibold ${TONE_TEXT[row.tone]}`}>
                  {row.value}
                </span>
              </div>
              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-ink-100 dark:bg-ink-800">
                <div
                  className={`animate-bar-grow h-full rounded-full ${TONE_BAR[row.tone]}`}
                  style={{
                    width: `${row.fill}%`,
                    animationDelay: `${300 + index * 140}ms`,
                  }}
                />
              </div>
            </li>
          ))}
        </ul>

        {/* Pulse trace */}
        <svg
          viewBox="0 0 320 44"
          className="mt-6 w-full"
          fill="none"
          preserveAspectRatio="none"
        >
          <defs>
            <linearGradient id="hero-trace" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%" stopColor="var(--color-accent-teal)" />
              <stop offset="55%" stopColor="var(--color-accent-blue)" />
              <stop offset="100%" stopColor="var(--color-accent-magenta)" />
            </linearGradient>
          </defs>
          <path
            className="animate-trace"
            d="M0 22h48l10-13 9 26 11-19 8 6h40l10-15 10 30 12-21 9 7h44l10-11 9 22 11-17 8 6h71"
            stroke="url(#hero-trace)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </div>

      {/* Floating conclusions */}
      <div className="animate-rise-in absolute top-44 -left-40 hidden rounded-xl border border-ink-200 bg-ink-0/95 px-3.5 py-2.5 shadow-xl backdrop-blur-md lg:block dark:border-ink-800 dark:bg-ink-900/95 [animation-delay:900ms]">
        <p className="text-[11px] font-semibold text-ink-950 dark:text-ink-0">
          Iron-deficiency pattern
        </p>
        <p className="text-[10px] text-ink-500">possible · low confidence</p>
      </div>

      <div className="animate-rise-in absolute -right-3 bottom-8 rounded-xl bg-gradient-to-br from-accent-violet to-accent-blue px-4 py-2.5 shadow-lg shadow-accent-violet/30 sm:-right-8 [animation-delay:1200ms]">
        <p className="text-[10px] font-medium uppercase tracking-wider text-white/80">
          Suggested specialty
        </p>
        <p className="text-sm font-bold text-white">Haematology</p>
      </div>
    </div>
  );
}
