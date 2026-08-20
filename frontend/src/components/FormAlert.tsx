interface FormAlertProps {
  message: string;
  /** Optional action rendered beneath the message, e.g. a recovery link. */
  action?: React.ReactNode;
}

/** Form-level error banner. Announced immediately to screen readers. */
export function FormAlert({ message, action }: FormAlertProps) {
  return (
    <div
      role="alert"
      className="rounded-xl border border-danger-500/40 bg-danger-500/8 px-4 py-3 dark:bg-danger-500/12"
    >
      <p className="text-sm text-ink-950 dark:text-ink-0">{message}</p>
      {action && <div className="mt-2 text-sm">{action}</div>}
    </div>
  );
}
