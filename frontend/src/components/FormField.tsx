import { useId, type InputHTMLAttributes } from 'react';

interface FormFieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  label: string;
  /** Validation message; also marks the input as invalid for assistive tech. */
  error?: string | undefined;
  hint?: string | undefined;
}

/** A labelled text input with accessible error and hint wiring. */
export function FormField({ label, error, hint, ...inputProps }: FormFieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  const hintId = `${id}-hint`;
  const describedBy = [error ? errorId : null, hint ? hintId : null]
    .filter(Boolean)
    .join(' ');

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-semibold">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy || undefined}
        className={`w-full rounded-xl border bg-ink-0 px-4 py-3 text-base transition placeholder:text-ink-400 focus:outline-none focus-visible:ring-2 dark:bg-ink-900 ${
          error
            ? 'border-danger-500 focus-visible:ring-danger-500/40'
            : 'border-ink-300 focus-visible:border-ink-950 focus-visible:ring-ink-950/15 dark:border-ink-700 dark:focus-visible:border-ink-0 dark:focus-visible:ring-ink-0/20'
        }`}
        {...inputProps}
      />
      {hint && !error && (
        <p id={hintId} className="text-xs text-ink-500">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="text-xs font-medium text-danger-600 dark:text-danger-400">
          {error}
        </p>
      )}
    </div>
  );
}
