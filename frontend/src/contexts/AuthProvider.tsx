import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { AuthContext, type AuthContextValue, type AuthStatus } from '@/contexts/auth';
import { authService } from '@/services/authService';
import { setAccessToken } from '@/services/apiClient';
import { installSessionRecovery } from '@/services/sessionRecovery';
import type { LoginPayload, SignupPayload, User } from '@/types/auth';

interface AuthProviderProps {
  children: ReactNode;
}

/**
 * Owns the authenticated session.
 *
 * On mount it attempts a silent refresh: the access token lives only in memory,
 * so after a page reload the httpOnly refresh cookie is the only thing that can
 * restore the session. Until that resolves the status is `initialising`, which
 * is what stops route guards from bouncing a signed-in user to /login.
 */
export function AuthProvider({ children }: AuthProviderProps) {
  const [status, setStatus] = useState<AuthStatus>('initialising');
  const [user, setUserState] = useState<User | null>(null);

  const clearSession = useCallback(() => {
    setAccessToken(null);
    setUserState(null);
    setStatus('anonymous');
  }, []);

  useEffect(() => {
    installSessionRecovery(clearSession);
  }, [clearSession]);

  useEffect(() => {
    let active = true;

    authService
      .refresh()
      .then((session) => {
        if (!active) return;
        if (session) {
          setUserState(session.user);
          setStatus('authenticated');
        } else {
          setStatus('anonymous');
        }
      })
      .catch(() => {
        if (active) setStatus('anonymous');
      });

    return () => {
      active = false;
    };
  }, []);

  const login = useCallback(async (payload: LoginPayload) => {
    const session = await authService.login(payload);
    setUserState(session.user);
    setStatus('authenticated');
    return session.user;
  }, []);

  const signup = useCallback(async (payload: SignupPayload) => {
    const session = await authService.signup(payload);
    setUserState(session.user);
    setStatus('authenticated');
    return session.user;
  }, []);

  const loginWithGoogle = useCallback(async (idToken: string) => {
    const session = await authService.loginWithGoogle(idToken);
    setUserState(session.user);
    setStatus('authenticated');
    return session.user;
  }, []);

  const logout = useCallback(async () => {
    await authService.logout();
    clearSession();
  }, [clearSession]);

  const setUser = useCallback((next: User) => setUserState(next), []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, login, signup, loginWithGoogle, logout, setUser }),
    [status, user, login, signup, loginWithGoogle, logout, setUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
