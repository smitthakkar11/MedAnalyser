import { useId, type SelectHTMLAttributes } from 'react';

interface Option<T extends string> {
  value: T;
  label: string;
}

interface SelectProps<T extends string>
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'id' | 'value' | 'onChange'> {
  label: string;
  value: T | null;
  options: readonly Option<T>[];
  onValueChange: (value: T | null) => void;
  /** Label for the empty choice. Omit to make the field required. */
  placeholder?: string;
  error?: string | undefined;
}

/** A labelled select with an optional "not answered" choice. */
export function Select<T extends string>({
  label,
  value,
  options,
  onValueChange,
  placeholder,
  error,
  ...selectProps
}: SelectProps<T>) {
  const id = useId();
  const errorId = `${id}-error`;

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-semibold">
        {label}
      </label>
      <select
        id={id}
        value={value ?? ''}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        onChange={(event) => onValueChange((event.target.value || null) as T | null)}
        className="w-full appearance-none rounded-xl border border-ink-300 bg-ink-0 px-4 py-3 text-base transition focus:outline-none focus-visible:border-ink-950 focus-visible:ring-2 focus-visible:ring-ink-950/15 dark:border-ink-700 dark:bg-ink-900 dark:focus-visible:border-ink-0 dark:focus-visible:ring-ink-0/20"
        {...selectProps}
      >
        {placeholder && <option value="">{placeholder}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && (
        <p id={errorId} className="text-xs font-medium text-danger-600 dark:text-danger-400">
          {error}
        </p>
      )}
    </div>
  );
}
