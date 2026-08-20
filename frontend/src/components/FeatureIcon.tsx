export type FeatureIconName = 'stethoscope' | 'chat' | 'evidence' | 'shield';

const PATHS: Record<FeatureIconName, React.ReactNode> = {
  stethoscope: (
    <>
      <path d="M4 3v6a5 5 0 0 0 10 0V3" />
      <path d="M2 3h3M13 3h3" />
      <path d="M9 14v2a5 5 0 0 0 10 0v-1" />
      <circle cx="19" cy="12" r="2.5" />
    </>
  ),
  chat: (
    <>
      <path d="M21 12a8 8 0 0 1-8 8H7l-4 3V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8Z" />
      <path d="M9 11h.01M13 11h.01M17 11h.01" />
    </>
  ),
  evidence: (
    <>
      <path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h5M8 17h8" />
    </>
  ),
  shield: (
    <>
      <path d="M12 2 4 5.5V11c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5.5Z" />
      <path d="M9 12l2 2 4-4" />
    </>
  ),
};

interface FeatureIconProps {
  name: FeatureIconName;
  className?: string;
}

/** Inline outline icon — no icon library, no network request. */
export function FeatureIcon({ name, className = 'size-5' }: FeatureIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.75"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {PATHS[name]}
    </svg>
  );
}
