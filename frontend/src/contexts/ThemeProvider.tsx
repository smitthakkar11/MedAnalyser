import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import {
  THEME_STORAGE_KEY,
  ThemeContext,
  type ThemeContextValue,
  type ThemePreference,
  readStoredPreference,
  resolveTheme,
} from '@/contexts/theme';

interface ThemeProviderProps {
  children: ReactNode;
}

/**
 * Owns the colour-theme preference.
 *
 * `system` follows the OS and keeps following it live; an explicit choice is
 * persisted and always wins. The `dark` class is applied to <html> so Tailwind's
 * `dark:` variant (configured as a class variant in index.css) picks it up.
 */
export function ThemeProvider({ children }: ThemeProviderProps) {
  const [preference, setPreferenceState] = useState<ThemePreference>(readStoredPreference);
  const [resolved, setResolved] = useState(() => resolveTheme(readStoredPreference()));

  // Apply the resolved theme to the document.
  useEffect(() => {
    document.documentElement.classList.toggle('dark', resolved === 'dark');
  }, [resolved]);

  // Keep `system` live: react to the OS changing while the app is open.
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const sync = () => setResolved(resolveTheme(preference));
    sync();
    if (preference !== 'system') return;
    media.addEventListener('change', sync);
    return () => media.removeEventListener('change', sync);
  }, [preference]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Non-fatal: the theme still applies for this session.
    }
  }, []);

  const toggle = useCallback(() => {
    setPreferenceState((current) => {
      const next = resolveTheme(current) === 'dark' ? 'light' : 'dark';
      try {
        localStorage.setItem(THEME_STORAGE_KEY, next);
      } catch {
        // Non-fatal.
      }
      return next;
    });
  }, []);

  const value = useMemo<ThemeContextValue>(
    () => ({ preference, resolved, setPreference, toggle }),
    [preference, resolved, setPreference, toggle],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}
