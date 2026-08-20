import axios from 'axios';
import type { AxiosError, AxiosInstance, InternalAxiosRequestConfig } from 'axios';
import type { ApiErrorBody } from '@/types/api';
import type { FieldError } from '@/types/auth';

/**
 * Single axios instance for the whole application.
 *
 * When `VITE_API_BASE_URL` is empty the client uses relative URLs and the Vite
 * dev server (or a reverse proxy in production) forwards `/api` to the backend.
 * That keeps the browser same-origin, which is what we want once auth cookies
 * are introduced in Phase 2.
 */
const baseURL = import.meta.env.VITE_API_BASE_URL ?? '';

export const apiClient: AxiosInstance = axios.create({
  baseURL,
  timeout: 15_000,
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,
});

/** A request config, tagged once it has already been replayed after a refresh. */
export type RetryableConfig = InternalAxiosRequestConfig & { __isRetry?: boolean };

/** A normalised, presentable error. Never contains raw backend internals. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number | undefined;
  readonly requestId: string | undefined;
  /** Extra machine-readable context, e.g. `reason: 'google_link_required'`. */
  readonly details: Record<string, unknown>;
  /** The request that failed, so it can be replayed after a token refresh. */
  readonly config: RetryableConfig | undefined;

  constructor(
    message: string,
    code: string,
    status?: number,
    requestId?: string,
    details: Record<string, unknown> = {},
    config?: RetryableConfig,
  ) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.requestId = requestId;
    this.details = details;
    this.config = config;
  }

  /** Per-field messages from a 422, keyed by field name. */
  get fieldErrors(): Record<string, string> {
    const errors = this.details['errors'];
    if (!Array.isArray(errors)) return {};
    return Object.fromEntries(
      (errors as FieldError[])
        .filter((error) => error.field)
        .map((error) => [error.field, error.message]),
    );
  }
}

/**
 * The in-memory access token.
 *
 * Deliberately not in localStorage: anything readable by script is readable by
 * an XSS payload. Sessions survive a page reload via the httpOnly refresh
 * cookie, which script cannot read at all.
 */
let accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorBody>;
    const config = axiosError.config as RetryableConfig | undefined;
    const envelope = axiosError.response?.data?.error;
    if (envelope) {
      return new ApiError(
        envelope.message,
        envelope.code,
        axiosError.response?.status,
        envelope.request_id,
        envelope.details ?? {},
        config,
      );
    }
    if (axiosError.code === 'ECONNABORTED') {
      return new ApiError(
        'The request timed out. Please try again.',
        'timeout',
        undefined,
        undefined,
        {},
        config,
      );
    }
    return new ApiError(
      'Could not reach the MedAnalyser service.',
      'network_error',
      axiosError.response?.status,
      undefined,
      {},
      config,
    );
  }
  return new ApiError('An unexpected error occurred.', 'unknown_error');
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(toApiError(error)),
);

apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  if (accessToken) {
    config.headers.set('Authorization', `Bearer ${accessToken}`);
  }
  return config;
});
