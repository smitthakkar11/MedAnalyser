import { apiClient } from '@/services/apiClient';
import type { HealthResponse, ReadinessResponse } from '@/types/api';

/** Health endpoints. Used to surface backend connectivity in the UI. */
export const healthService = {
  async getHealth(signal: AbortSignal): Promise<HealthResponse> {
    const { data } = await apiClient.get<HealthResponse>('/api/health', { signal });
    return data;
  },

  async getReadiness(signal: AbortSignal): Promise<ReadinessResponse> {
    // Readiness answers 503 when a dependency is down; that is a meaningful
    // payload, not a transport failure, so accept it as a success.
    const { data } = await apiClient.get<ReadinessResponse>('/api/health/ready', {
      signal,
      validateStatus: (status) => status === 200 || status === 503,
    });
    return data;
  },
};
