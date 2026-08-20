import { apiClient, ApiError } from '@/services/apiClient';
import { authService } from '@/services/authService';

/**
 * Transparently recover from an expired access token.
 *
 * When a request fails with 401, exchange the refresh cookie for a new access
 * token once and replay the original request. Without this, a user would be
 * signed out every time the short-lived access token expired.
 *
 * Concurrent 401s share a single refresh so a burst of failing requests does
 * not trigger a burst of refresh calls.
 */

/** Endpoints that must never trigger a refresh-and-retry. */
const NON_RETRYABLE = ['/api/auth/refresh', '/api/auth/login', '/api/auth/signup'];

let inFlightRefresh: Promise<boolean> | null = null;

function refreshOnce(): Promise<boolean> {
  inFlightRefresh ??= authService
    .refresh()
    .then((result) => result !== null)
    .catch(() => false)
    .finally(() => {
      inFlightRefresh = null;
    });
  return inFlightRefresh;
}

let installed = false;

/** Install the interceptor. Safe to call more than once. */
export function installSessionRecovery(onSessionLost: () => void): void {
  if (installed) return;
  installed = true;

  apiClient.interceptors.response.use(
    (response) => response,
    async (error: unknown) => {
      if (!(error instanceof ApiError) || error.status !== 401) {
        return Promise.reject(error);
      }

      const config = error.config;
      if (!config || config.__isRetry || NON_RETRYABLE.some((p) => config.url?.startsWith(p))) {
        return Promise.reject(error);
      }

      const recovered = await refreshOnce();
      if (!recovered) {
        onSessionLost();
        return Promise.reject(error);
      }

      config.__isRetry = true;
      return apiClient.request(config);
    },
  );
}
