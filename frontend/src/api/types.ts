// Mirrors backend/schemas/auth.py

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface RegisterResponse {
  message: string
  user_id: string
  verified: boolean
}

export interface User {
  id: string
  username: string
  email: string
  verified: boolean
}

export interface RegisterPayload {
  username: string
  email: string
  password: string
  confirm_password: string
}

export interface LoginPayload {
  email: string
  password: string
}

/** /auth/verify, /auth/resend-verification, /users/me/email all return just a message. */
export interface MessageResponse {
  message: string
}

export interface UpdateEmailPayload {
  new_email: string
  current_password: string
}

export interface DeleteAccountPayload {
  current_password: string
}

export interface ResetPasswordPayload {
  current_password: string
  new_password: string
}
