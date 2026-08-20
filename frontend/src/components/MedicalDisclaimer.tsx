interface MedicalDisclaimerProps {
  /** `banner` for page sections, `inline` for a quieter footnote. */
  variant?: 'banner' | 'inline';
}

/**
 * The standing safety notice.
 *
 * This is the single place the wording lives, so it can never drift between
 * pages. Required by the product's safety rules: MedAnalyser must never present
 * itself as a diagnosis or a substitute for a clinician.
 */
export function MedicalDisclaimer({ variant = 'banner' }: MedicalDisclaimerProps) {
  if (variant === 'inline') {
    return (
      <p className="text-xs leading-relaxed text-ink-500">
        MedAnalyser provides AI-assisted health information. It does not provide a medical
        diagnosis and is not a substitute for a licensed healthcare professional. In an
        emergency, contact your local emergency services.
      </p>
    );
  }

  return (
    <aside
      role="note"
      aria-label="Medical disclaimer"
      className="flex items-start gap-4 border border-ink-200 bg-ink-50 px-6 py-5 dark:border-ink-800 dark:bg-ink-900"
    >
      <svg
        viewBox="0 0 24 24"
        className="mt-0.5 size-5 shrink-0 text-danger-500 dark:text-danger-400"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z" />
        <path d="M12 9v4" />
        <path d="M12 17h.01" />
      </svg>
      <p className="text-sm leading-relaxed text-ink-700 dark:text-ink-300">
        <span className="font-semibold text-ink-950 dark:text-ink-0">
          Information, not a diagnosis.
        </span>{' '}
        MedAnalyser highlights what may be relevant and what to ask about — it does not diagnose
        conditions or prescribe medication. Always confirm with a qualified clinician, and seek
        urgent care for severe or worsening symptoms.
      </p>
    </aside>
  );
}
