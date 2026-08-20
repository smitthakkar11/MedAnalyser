/** Shared API contract types, mirroring the backend Pydantic schemas. */

export type ComponentStatus = 'ok' | 'degraded' | 'unavailable';

export interface DependencyHealth {
  name: string;
  status: ComponentStatus;
  detail: string | null;
  latency_ms: number | null;
}

export interface HealthResponse {
  status: ComponentStatus;
  app: string;
  version: string;
  environment: string;
}

export interface ReadinessResponse extends HealthResponse {
  dependencies: DependencyHealth[];
}

/** Error envelope returned by the backend for every failed request. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id?: string;
  };
}
