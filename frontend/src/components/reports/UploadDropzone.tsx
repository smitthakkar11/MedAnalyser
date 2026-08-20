import { useRef, useState, type DragEvent } from 'react';

interface UploadDropzoneProps {
  onFile: (file: File) => void;
  pending: boolean;
  maxSizeMb?: number;
}

/** Drag-and-drop or click-to-browse for a single PDF. */
export function UploadDropzone({ onFile, pending, maxSizeMb = 20 }: UploadDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);

  function handleDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files[0];
    if (file) onFile(file);
  }

  return (
    <div
      onDragOver={(event) => {
        event.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`rounded-2xl border-2 border-dashed px-6 py-12 text-center transition ${
        dragging
          ? 'border-accent-blue bg-accent-blue/6'
          : 'border-ink-300 dark:border-ink-700'
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        className="sr-only"
        disabled={pending}
        onChange={(event) => {
          const file = event.target.files?.[0];
          if (file) onFile(file);
          // Reset so re-picking the same file fires change again.
          event.target.value = '';
        }}
      />

      <svg
        viewBox="0 0 24 24"
        className="mx-auto size-10 text-ink-400"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        aria-hidden="true"
      >
        <path d="M6 2h9l5 5v13a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2Z" />
        <path d="M14 2v6h6" />
        <path d="M12 18v-6M9 15l3-3 3 3" />
      </svg>

      <p className="mt-4 font-semibold">
        {pending ? 'Reading your report…' : 'Drop a PDF here'}
      </p>
      <p className="mt-1 text-sm text-ink-600 dark:text-ink-400">
        PDF only, up to {maxSizeMb} MB. Scanned reports are read with OCR.
      </p>

      <button
        type="button"
        disabled={pending}
        onClick={() => inputRef.current?.click()}
        className="mt-5 rounded-xl bg-gradient-to-r from-accent-blue to-accent-violet px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-accent-violet/20 transition hover:shadow-xl disabled:opacity-60"
      >
        {pending ? 'Uploading…' : 'Choose a file'}
      </button>
    </div>
  );
}
