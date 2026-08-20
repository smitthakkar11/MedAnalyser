import { humaniseSymptom } from '@/types/assessment';

interface SymptomChipsProps {
  symptoms: string[];
  tone?: 'positive' | 'negative';
  emptyLabel?: string;
}

/** Read-only chips showing what the system understood. */
export function SymptomChips({ symptoms, tone = 'positive', emptyLabel }: SymptomChipsProps) {
  if (symptoms.length === 0) {
    return emptyLabel ? <p className="text-sm text-ink-500">{emptyLabel}</p> : null;
  }

  const style =
    tone === 'positive'
      ? 'border-accent-teal/40 bg-accent-teal/10'
      : 'border-ink-300 bg-ink-100 text-ink-600 line-through dark:border-ink-700 dark:bg-ink-900 dark:text-ink-400';

  return (
    <ul className="flex flex-wrap gap-2">
      {symptoms.map((symptom) => (
        <li key={symptom} className={`rounded-full border px-3 py-1.5 text-sm ${style}`}>
          {humaniseSymptom(symptom)}
        </li>
      ))}
    </ul>
  );
}
