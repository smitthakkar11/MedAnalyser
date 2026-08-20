import type { ReactNode } from 'react';

interface RepeatableListProps<T> {
  items: T[];
  /**
   * Receives an updater rather than a finished array.
   *
   * The parent applies it against the *current* state, so two edits dispatched
   * before a re-render (adding a condition and a medication in quick
   * succession, say) both survive instead of the second clobbering the first.
   */
  onChange: (update: (items: T[]) => T[]) => void;
  /** A fresh blank item, added when the user clicks "Add". */
  emptyItem: T;
  /** Renders the editor for one item. */
  renderItem: (item: T, update: (patch: Partial<T>) => void, index: number) => ReactNode;
  addLabel: string;
  emptyMessage: string;
  /** Announced when a row is removed, e.g. "Remove allergy". */
  removeLabel: string;
}

/**
 * A list of editable records with add/remove.
 *
 * Rows are keyed by index because these items have no stable client-side id
 * until they are saved; the list is short and only ever edited in place, so an
 * index key does not cause the usual reconciliation problems.
 */
export function RepeatableList<T>({
  items,
  onChange,
  emptyItem,
  renderItem,
  addLabel,
  emptyMessage,
  removeLabel,
}: RepeatableListProps<T>) {
  function update(index: number, patch: Partial<T>) {
    onChange((current) =>
      current.map((item, i) => (i === index ? { ...item, ...patch } : item)),
    );
  }

  function remove(index: number) {
    onChange((current) => current.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-4">
      {items.length === 0 && (
        <p className="rounded-xl border border-dashed border-ink-300 px-4 py-6 text-center text-sm text-ink-500 dark:border-ink-700">
          {emptyMessage}
        </p>
      )}

      {items.map((item, index) => (
        // Index keys are safe here: rows are controlled by props, so a removal
        // re-renders every field from the new array rather than reusing state.
        <div
          key={index}
          className="relative rounded-xl border border-ink-200 bg-ink-50/60 p-4 dark:border-ink-800 dark:bg-ink-900/60"
        >
          <div className="grid gap-4 sm:grid-cols-2">{renderItem(item, (patch) => update(index, patch), index)}</div>
          <button
            type="button"
            onClick={() => remove(index)}
            aria-label={`${removeLabel} ${index + 1}`}
            className="mt-4 text-sm font-semibold text-danger-600 transition hover:underline dark:text-danger-400"
          >
            Remove
          </button>
        </div>
      ))}

      <button
        type="button"
        onClick={() => onChange((current) => [...current, { ...emptyItem }])}
        className="inline-flex items-center gap-2 rounded-full border border-ink-300 px-5 py-2.5 text-sm font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
      >
        <span aria-hidden="true">+</span>
        {addLabel}
      </button>
    </div>
  );
}
