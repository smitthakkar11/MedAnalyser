import { apiClient } from '@/services/apiClient';
import type { Dashboard, Profile, ProfileUpdate } from '@/types/profile';

export const profileService = {
  async getProfile(signal: AbortSignal): Promise<Profile> {
    const { data } = await apiClient.get<Profile>('/api/profile', { signal });
    return data;
  },

  /** Replaces the whole profile; the collections are sets, not deltas. */
  async updateProfile(payload: ProfileUpdate): Promise<Profile> {
    const { data } = await apiClient.put<Profile>('/api/profile', payload);
    return data;
  },

  async getDashboard(signal: AbortSignal): Promise<Dashboard> {
    const { data } = await apiClient.get<Dashboard>('/api/dashboard', { signal });
    return data;
  },
};
