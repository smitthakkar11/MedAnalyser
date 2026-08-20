import axios from 'axios';
import type { AxiosError, AxiosInstance } from 'axios';
import type { ApiErrorBody } from '@/types/api';

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

/** A normalised, presentable error. Never contains raw backend internals. */
export class ApiError extends Error {
  readonly code: string;
  readonly status: number | undefined;
  readonly requestId: string | undefined;

  constructor(message: string, code: string, status?: number, requestId?: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<ApiErrorBody>;
    const envelope = axiosError.response?.data?.error;
    if (envelope) {
      return new ApiError(
        envelope.message,
        envelope.code,
        axiosError.response?.status,
        envelope.request_id,
      );
    }
    if (axiosError.code === 'ECONNABORTED') {
      return new ApiError('The request timed out. Please try again.', 'timeout');
    }
    return new ApiError(
      'Could not reach the MedAnalyser service.',
      'network_error',
      axiosError.response?.status,
    );
  }
  return new ApiError('An unexpected error occurred.', 'unknown_error');
}

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(toApiError(error)),
);
