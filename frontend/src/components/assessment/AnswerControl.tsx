import { useState } from 'react';
import { FormField } from '@/components/FormField';
import type { AnswerValue, FollowUpQuestion } from '@/types/assessment';

interface AnswerControlProps {
  question: FollowUpQuestion;
  onSubmit: (value: AnswerValue) => void;
  pending: boolean;
}

/**
 * Renders the right input for a question's `answer_type`.
 *
 * The backend decides what to ask and how it should be answered; this component
 * only maps that to a control. Adding a question type means adding a case here
 * and an entry in the rule file — never branching on question keys.
 */
export function AnswerControl({ question, onSubmit, pending }: AnswerControlProps) {
  // State is per-question. The parent remounts this component for each new
  // question via `key`, so there is nothing to reset here — resetting in an
  // effect would cost an extra render pass on every question.
  const [text, setText] = useState('');
  const [selected, setSelected] = useState<string[]>([]);

  const buttonClass =
    'rounded-xl px-6 py-3 text-sm font-semibold transition disabled:opacity-50';
  const primary = `${buttonClass} bg-gradient-to-r from-accent-blue to-accent-violet text-white shadow-lg shadow-accent-violet/20 hover:shadow-xl`;
  const secondary = `${buttonClass} border border-ink-300 hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0`;

  if (question.answer_type === 'boolean') {
    return (
      <div className="flex flex-wrap gap-3">
        <button type="button" disabled={pending} className={primary} onClick={() => onSubmit(true)}>
          Yes
        </button>
        <button type="button" disabled={pending} className={secondary} onClick={() => onSubmit(false)}>
          No
        </button>
      </div>
    );
  }

  if (question.answer_type === 'choice') {
    return (
      <div className="flex flex-wrap gap-3">
        {question.choices.map((choice) => (
          <button
            key={choice}
            type="button"
            disabled={pending}
            className={secondary}
            onClick={() => onSubmit(choice)}
          >
            {choice.charAt(0).toUpperCase() + choice.slice(1)}
          </button>
        ))}
      </div>
    );
  }

  if (question.answer_type === 'symptom_check') {
    const toggle = (value: string) =>
      setSelected((current) =>
        current.includes(value)
          ? current.filter((item) => item !== value)
          : [...current, value],
      );

    return (
      <div className="space-y-5">
        <div className="flex flex-wrap gap-2">
          {question.symptom_options.map((option) => {
            const isOn = selected.includes(option.value);
            return (
              <button
                key={option.value}
                type="button"
                aria-pressed={isOn}
                onClick={() => toggle(option.value)}
                className={`rounded-full border px-4 py-2 text-sm font-medium transition ${
                  isOn
                    ? 'border-accent-blue bg-accent-blue/12 text-ink-950 dark:text-ink-0'
                    : 'border-ink-300 hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0'
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            disabled={pending}
            className={primary}
            onClick={() => onSubmit(selected)}
          >
            {selected.length > 0 ? `Confirm ${selected.length} selected` : 'None of these'}
          </button>
        </div>
      </div>
    );
  }

  const isDuration = question.answer_type === 'duration';
  const isNumber = question.answer_type === 'number' || isDuration;

  return (
    <form
      className="space-y-4"
      onSubmit={(event) => {
        event.preventDefault();
        const trimmed = text.trim();
        onSubmit(isNumber ? (trimmed ? Number(trimmed) : null) : trimmed || null);
      }}
    >
      <FormField
        label={isDuration ? 'Number of days' : 'Your answer'}
        type={isNumber ? 'number' : 'text'}
        min={isNumber ? 0 : undefined}
        step={isDuration ? '0.5' : undefined}
        value={text}
        onChange={(event) => setText(event.target.value)}
        placeholder={isDuration ? 'e.g. 3' : ''}
        autoFocus
      />
      <div className="flex flex-wrap gap-3">
        <button type="submit" disabled={pending} className={primary}>
          Continue
        </button>
        <button
          type="button"
          disabled={pending}
          className={secondary}
          onClick={() => onSubmit(null)}
        >
          Skip
        </button>
      </div>
    </form>
  );
}
