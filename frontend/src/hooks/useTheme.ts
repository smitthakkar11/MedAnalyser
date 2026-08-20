import { useContext } from 'react';
import { ThemeContext, type ThemeContextValue } from '@/contexts/theme';

/** Access the current colour theme. Must be used inside `<ThemeProvider>`. */
export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}
