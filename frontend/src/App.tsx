import { BrowserRouter, Route, Routes } from 'react-router-dom';
import { AuthProvider } from '@/contexts/AuthProvider';
import { ThemeProvider } from '@/contexts/ThemeProvider';
import {
  RedirectIfAuthenticated,
  RequireAuth,
  RequireSession,
} from '@/components/RouteGuards';
import { AppLayout } from '@/layouts/AppLayout';
import { AuthLayout } from '@/layouts/AuthLayout';
import { PublicLayout } from '@/layouts/PublicLayout';
import { AssessmentDetailPage } from '@/pages/AssessmentDetailPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { HistoryPage } from '@/pages/HistoryPage';
import { NewAssessmentPage } from '@/pages/NewAssessmentPage';
import { ReportDetailPage } from '@/pages/ReportDetailPage';
import { ReportsPage } from '@/pages/ReportsPage';
import { LandingPage } from '@/pages/LandingPage';
import { LoginPage } from '@/pages/LoginPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { ProfilePage } from '@/pages/ProfilePage';
import { OnboardingPage } from '@/pages/OnboardingPage';
import { SignupPage } from '@/pages/SignupPage';

/**
 * Application routes.
 *
 * Three guard levels:
 *   - `RedirectIfAuthenticated` — /login and /signup bounce signed-in users on.
 *   - `RequireSession`          — signed in, onboarding not necessarily done.
 *   - `RequireAuth`             — signed in *and* age-verified. Everything that
 *                                 touches medical data lives behind this.
 *
 * Guards control navigation only; the backend authorises every request
 * independently.
 */
export default function App() {
  return (
    <ThemeProvider>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route element={<PublicLayout />}>
              <Route index element={<LandingPage />} />
            </Route>

            <Route element={<AuthLayout />}>
              <Route element={<RedirectIfAuthenticated />}>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/signup" element={<SignupPage />} />
              </Route>
              <Route element={<RequireSession />}>
                <Route path="/onboarding" element={<OnboardingPage />} />
              </Route>
            </Route>

            <Route element={<RequireAuth />}>
              <Route element={<AppLayout />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/profile" element={<ProfilePage />} />
                <Route path="/assessment/new" element={<NewAssessmentPage />} />
                <Route path="/assessment/:id" element={<AssessmentDetailPage />} />
                <Route path="/history" element={<HistoryPage />} />
                <Route path="/reports" element={<ReportsPage />} />
                <Route path="/reports/:id" element={<ReportDetailPage />} />
              </Route>
            </Route>

            <Route element={<PublicLayout />}>
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </ThemeProvider>
  );
}
