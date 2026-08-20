import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <div className="mx-auto max-w-[1400px] px-6 py-32 lg:px-10">
      <p className="font-mono text-sm text-ink-500">404</p>
      <h1 className="mt-4 max-w-[12ch] text-headline">This page doesn&rsquo;t exist.</h1>
      <p className="mt-6 max-w-md text-lg text-ink-600 dark:text-ink-400">
        The page you are looking for may have moved, or the link may be incorrect.
      </p>
      <Link
        to="/"
        className="group mt-10 inline-flex items-center gap-2 rounded-full bg-ink-950 px-7 py-4 text-base font-semibold text-ink-0 transition hover:bg-ink-800 dark:bg-ink-0 dark:text-ink-950 dark:hover:bg-ink-200"
      >
        Back to home
        <span aria-hidden="true" className="transition-transform group-hover:translate-x-1">
          →
        </span>
      </Link>
    </div>
  );
}
