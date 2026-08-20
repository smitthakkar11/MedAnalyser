interface GoogleButtonProps {
  onClick: () => void;
  disabled?: boolean;
  label?: string;
}

/**
 * "Continue with Google" button.
 *
 * The client id is public by design and comes from `VITE_GOOGLE_CLIENT_ID`; the
 * client *secret* never reaches the browser. When no client id is configured
 * the button is rendered disabled with an explanation rather than hidden, so
 * the state of the integration is obvious.
 */
export function GoogleButton({ onClick, disabled, label = 'Continue with Google' }: GoogleButtonProps) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="inline-flex w-full items-center justify-center gap-3 rounded-xl border border-ink-300 bg-ink-0 px-6 py-3.5 text-base font-semibold transition hover:border-ink-950 disabled:cursor-not-allowed disabled:opacity-50 dark:border-ink-700 dark:bg-ink-900 dark:hover:border-ink-0"
    >
      <svg viewBox="0 0 18 18" className="size-5" aria-hidden="true">
        <path
          fill="#4285F4"
          d="M17.64 9.2c0-.64-.06-1.25-.16-1.84H9v3.48h4.84a4.14 4.14 0 0 1-1.8 2.72v2.26h2.92c1.7-1.57 2.68-3.88 2.68-6.62Z"
        />
        <path
          fill="#34A853"
          d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.92-2.26c-.81.54-1.84.86-3.04.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.33A9 9 0 0 0 9 18Z"
        />
        <path
          fill="#FBBC05"
          d="M3.97 10.72a5.4 5.4 0 0 1 0-3.44V4.95H.96a9 9 0 0 0 0 8.1l3.01-2.33Z"
        />
        <path
          fill="#EA4335"
          d="M9 3.58c1.32 0 2.5.45 3.44 1.35l2.58-2.58C13.46.89 11.43 0 9 0A9 9 0 0 0 .96 4.95l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58Z"
        />
      </svg>
      {label}
    </button>
  );
}
