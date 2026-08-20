import { Link, NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Logo } from '@/components/Logo';
import { MedicalDisclaimer } from '@/components/MedicalDisclaimer';
import { ThemeToggle } from '@/components/ThemeToggle';
import { useAuth } from '@/hooks/useAuth';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/history', label: 'Assessments' },
  { to: '/profile', label: 'Profile' },
] as const;

/** Chrome for the signed-in application. */
export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleSignOut() {
    await logout();
    navigate('/', { replace: true });
  }

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
          <div className="flex items-center gap-8">
            <Link to="/dashboard" aria-label="MedAnalyser dashboard">
              <Logo />
            </Link>
            <nav aria-label="Primary" className="hidden gap-6 sm:flex">
              {NAV_ITEMS.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    `text-sm font-semibold transition ${
                      isActive
                        ? 'text-ink-950 dark:text-ink-0'
                        : 'text-ink-600 hover:text-ink-950 dark:text-ink-400 dark:hover:text-ink-0'
                    }`
                  }
                >
                  {item.label}
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-2 sm:gap-3">
            <ThemeToggle />
            {user && (
              <span className="hidden text-sm text-ink-600 md:inline dark:text-ink-400">
                {user.email}
              </span>
            )}
            <button
              type="button"
              onClick={() => void handleSignOut()}
              className="whitespace-nowrap rounded-full border border-ink-300 px-4 py-2 text-sm font-semibold transition hover:border-ink-950 dark:border-ink-700 dark:hover:border-ink-0"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      <main id="main" className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-10 lg:px-10">
        <Outlet />
      </main>

      <footer className="border-t border-ink-200 dark:border-ink-800">
        <div className="mx-auto max-w-[1400px] px-6 py-8 lg:px-10">
          <MedicalDisclaimer variant="inline" />
        </div>
      </footer>
    </div>
  );
}
