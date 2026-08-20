import { apiClient, ApiError, setAccessToken } from '@/services/apiClient';
import type { AuthResponse, LoginPayload, SignupPayload, User } from '@/types/auth';

const AUTH = '/api/auth';

/** Backend `details.reason` when an email already has a password account. */
export const GOOGLE_LINK_REQUIRED = 'google_link_required';

export const authService = {
  async signup(payload: SignupPayload): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>(`${AUTH}/signup`, payload);
    setAccessToken(data.access_token);
    return data;
  },

  async login(payload: LoginPayload): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>(`${AUTH}/login`, payload);
    setAccessToken(data.access_token);
    return data;
  },

  async loginWithGoogle(idToken: string): Promise<AuthResponse> {
    const { data } = await apiClient.post<AuthResponse>(`${AUTH}/google`, {
      id_token: idToken,
    });
    setAccessToken(data.access_token);
    return data;
  },

  async linkGoogle(idToken: string): Promise<User> {
    const { data } = await apiClient.post<User>(`${AUTH}/link-google`, { id_token: idToken });
    return data;
  },

  async logout(): Promise<void> {
    try {
      await apiClient.post(`${AUTH}/logout`);
    } finally {
      // The local session ends even if the server call failed.
      setAccessToken(null);
    }
  },

  async me(signal?: AbortSignal): Promise<User> {
    const { data } = await apiClient.get<User>(
      `${AUTH}/me`,
      signal ? { signal } : undefined,
    );
    return data;
  },

  async completeOnboarding(dateOfBirth: string): Promise<User> {
    const { data } = await apiClient.post<User>(`${AUTH}/onboarding`, {
      date_of_birth: dateOfBirth,
    });
    return data;
  },

  /**
   * Exchange the httpOnly refresh cookie for a new access token.
   *
   * Returns null when there is no usable session, which is the normal case for
   * a first-time visitor rather than an error worth surfacing.
   */
  async refresh(): Promise<AuthResponse | null> {
    try {
      const { data } = await apiClient.post<AuthResponse>(`${AUTH}/refresh`);
      setAccessToken(data.access_token);
      return data;
    } catch (error) {
      setAccessToken(null);
      if (error instanceof ApiError && error.status === 401) return null;
      throw error;
    }
  },
};
