import { Link, Outlet } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { ThemeToggle } from '@/components/ThemeToggle';

/** Focused, distraction-free chrome for the sign-in and onboarding flow. */
export function AuthLayout() {
  return (
    <div className="relative isolate flex min-h-full flex-col overflow-hidden bg-ink-0 text-ink-950 dark:bg-ink-950 dark:text-ink-0">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 -z-10">
        <div className="animate-drift absolute -left-40 -top-40 size-[34rem] rounded-full bg-accent-violet/12 blur-3xl dark:bg-accent-violet/18" />
        <div className="animate-float-slow absolute -right-32 bottom-0 size-[30rem] rounded-full bg-accent-teal/12 blur-3xl dark:bg-accent-teal/16" />
      </div>

      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <Link to="/" aria-label="MedAnalyser home">
          <Logo />
        </Link>
        <ThemeToggle />
      </header>

      <main id="main" className="flex flex-1 items-center justify-center px-6 py-8">
        <div className="w-full max-w-md">
          <Outlet />
        </div>
      </main>

      <footer className="mx-auto w-full max-w-md px-6 pb-10">
        <MedicalDisclaimer variant="inline" />
      </footer>
    </div>
  );
}
