import type { ReactNode } from 'react';

interface SubmitButtonProps {
  pending: boolean;
  children: ReactNode;
  pendingLabel?: string;
}

/** Primary form submit button with a busy state that blocks double submission. */
export function SubmitButton({ pending, children, pendingLabel = 'Working' }: SubmitButtonProps) {
  return (
    <button
      type="submit"
      disabled={pending}
      className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent-blue to-accent-violet px-6 py-3.5 text-base font-semibold text-white shadow-lg shadow-accent-violet/20 transition hover:shadow-xl hover:shadow-accent-violet/35 disabled:cursor-not-allowed disabled:opacity-60 disabled:shadow-none"
    >
      {pending && (
        <span
          aria-hidden="true"
          className="size-4 animate-spin rounded-full border-2 border-white/40 border-t-white"
        />
      )}
      {pending ? `${pendingLabel}…` : children}
    </button>
  );
}
