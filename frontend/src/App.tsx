import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { ThemeProvider } from '@/contexts/ThemeProvider';
import { PublicLayout } from '@/layouts/PublicLayout';
import { LandingPage } from '@/pages/LandingPage';
import { NotFoundPage } from '@/pages/NotFoundPage';

/**
 * Application routes.
 *
 * Phase 1 ships the public shell only. Authenticated routes (/dashboard,
 * /assessment/*, /reports/*, /history, /timeline, /settings) arrive with the
 * auth guard in Phase 2 — they are deliberately absent rather than stubbed, so
 * no route can appear protected while it is not.
 */
export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<PublicLayout />}>
            <Route index element={<LandingPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}
