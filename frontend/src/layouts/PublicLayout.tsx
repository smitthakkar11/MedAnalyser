import { Link, Outlet } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { ThemeToggle } from '@/components/ThemeToggle';

const FOOTER_LINKS = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Safety', href: '#safety' },
  { label: 'System status', href: '#system-status' },
] as const;

/** Chrome for unauthenticated, publicly reachable pages. */
export function PublicLayout() {
  return (
    <div className="flex min-h-full flex-col bg-ink-0 text-ink-950 dark:bg-ink-950 dark:text-ink-0">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-ink-950 focus:px-4 focus:py-2 focus:text-ink-0 dark:focus:bg-ink-0 dark:focus:text-ink-950"
      >
        Skip to content
      </a>

      <header className="sticky top-0 z-40 border-b border-ink-200 bg-ink-0/85 backdrop-blur-md dark:border-ink-800 dark:bg-ink-950/85">
        <div className="mx-auto flex max-w-[1400px] items-center justify-between gap-6 px-6 py-4 lg:px-10">
          <Link to="/" aria-label="MedAnalyser home">
            <Logo />
          </Link>

          <div className="flex items-center gap-2 sm:gap-3">
            <ThemeToggle />
            <Link
              to="/login"
              className="hidden whitespace-nowrap rounded-full px-4 py-2.5 text-sm font-semibold text-ink-700 transition hover:text-ink-950 sm:inline-flex dark:text-ink-400 dark:hover:text-ink-0"
            >
              Sign in
            </Link>
            <Link
              to="/signup"
              className="inline-flex whitespace-nowrap rounded-full bg-ink-950 px-4 py-2.5 text-sm font-semibold text-ink-0 transition hover:bg-ink-800 sm:px-5 dark:bg-ink-0 dark:text-ink-950 dark:hover:bg-ink-200"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      <main id="main" className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-ink-200 dark:border-ink-800">
        <div className="mx-auto max-w-[1400px] px-6 py-12 lg:px-10">
          <div className="flex flex-col gap-8 border-b border-ink-200 pb-10 sm:flex-row sm:items-start sm:justify-between dark:border-ink-800">
            <Logo />
            <nav aria-label="Footer" className="flex flex-wrap gap-x-8 gap-y-3">
              {FOOTER_LINKS.map((link) => (
                <a
                  key={link.href}
                  href={link.href}
                  className="text-sm font-medium text-ink-600 transition hover:text-ink-950 dark:text-ink-400 dark:hover:text-ink-0"
                >
                  {link.label}
                </a>
              ))}
            </nav>
          </div>

          <div className="mt-8 max-w-3xl space-y-4">
            <MedicalDisclaimer variant="inline" />
            <p className="text-xs text-ink-500">© {new Date().getFullYear()} MedAnalyser</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
