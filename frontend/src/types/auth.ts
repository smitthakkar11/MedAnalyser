/** Authentication contract types, mirroring the backend Pydantic schemas. */

export interface User {
  id: string;
  name: string;
  email: string;
  date_of_birth: string | null;
  onboarding_complete: boolean;
  has_password: boolean;
  linked_providers: string[];
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  /** Access token lifetime in seconds. */
  expires_in: number;
  user: User;
}

export interface SignupPayload {
  name: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

/** A field-level validation failure returned by the backend. */
export interface FieldError {
  type: string;
  field: string;
  message: string;
}
