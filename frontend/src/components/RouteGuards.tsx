import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '@/hooks/useAuth';
import { FullPageSpinner } from '@/components/FullPageSpinner';

/**
 * Route guards.
 *
 * These control *navigation only*. Every protected resource is also
 * authorised server-side — the backend never trusts the client to decide who
 * may read what. A guard that can be bypassed in devtools must never be the
 * thing standing between one user and another user's medical data.
 */

/** Requires a signed-in user who has completed onboarding. */
export function RequireAuth() {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === 'initialising') return <FullPageSpinner label="Restoring your session" />;

  if (status === 'anonymous' || !user) {
    // Remember where they were headed so login can return them there.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (!user.onboarding_complete) {
    return <Navigate to="/onboarding" replace />;
  }

  return <Outlet />;
}

/** Requires a signed-in user, whether or not onboarding is complete. */
export function RequireSession() {
  const { status, user } = useAuth();
  const location = useLocation();

  if (status === 'initialising') return <FullPageSpinner label="Restoring your session" />;
  if (status === 'anonymous' || !user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

/** For /login and /signup: sends an already-signed-in user onwards. */
export function RedirectIfAuthenticated() {
  const { status, user } = useAuth();

  if (status === 'initialising') return <FullPageSpinner label="Loading" />;
  if (status === 'authenticated' && user) {
    return <Navigate to={user.onboarding_complete ? '/dashboard' : '/onboarding'} replace />;
  }
  return <Outlet />;
}
