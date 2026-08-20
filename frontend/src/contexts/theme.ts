import { createContext } from 'react';

export type ThemePreference = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

/** Key used for the persisted preference. Kept in sync with the inline
 *  no-flash script in `index.html` — change both together. */
export const THEME_STORAGE_KEY = 'medanalyser.theme';

export interface ThemeContextValue {
  /** What the user chose, including `system`. */
  preference: ThemePreference;
  /** What is actually rendered right now. */
  resolved: ResolvedTheme;
  setPreference: (preference: ThemePreference) => void;
  /** Flip between light and dark, leaving `system` behind. */
  toggle: () => void;
}

export const ThemeContext = createContext<ThemeContextValue | null>(null);

/** Read the stored preference, tolerating absent or corrupted storage. */
export function readStoredPreference(): ThemePreference {
  try {
    const stored = localStorage.getItem(THEME_STORAGE_KEY);
    if (stored === 'light' || stored === 'dark' || stored === 'system') {
      return stored;
    }
  } catch {
    // Storage can be unavailable (private mode, blocked cookies) — fall back.
  }
  return 'system';
}

export function systemTheme(): ResolvedTheme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function resolveTheme(preference: ThemePreference): ResolvedTheme {
  return preference === 'system' ? systemTheme() : preference;
}
