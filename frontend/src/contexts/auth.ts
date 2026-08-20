import { createContext } from 'react';
import type { LoginPayload, SignupPayload, User } from '@/types/auth';

/** Where the session is in its lifecycle. */
export type AuthStatus = 'initialising' | 'authenticated' | 'anonymous';

export interface AuthContextValue {
  status: AuthStatus;
  user: User | null;
  login: (payload: LoginPayload) => Promise<User>;
  signup: (payload: SignupPayload) => Promise<User>;
  loginWithGoogle: (idToken: string) => Promise<User>;
  logout: () => Promise<void>;
  /** Replace the cached user after a mutation such as onboarding. */
  setUser: (user: User) => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
