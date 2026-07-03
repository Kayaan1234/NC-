// Mirrors backend/schemas/auth.py

/** Body of /auth/login and /auth/refresh. The refresh token is NOT here — the
 *  backend delivers it only as an httpOnly cookie. `user_id`/`verified` come
 *  back too, but the client re-pulls /users/me for its user state, so only
 *  `access_token` is actually consumed. */
export interface TokenResponse {
  access_token: string
  user_id: string
  verified: boolean
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

export interface ForgotPasswordPayload {
  email: string
}

/** /auth/reset-password (the token flow) — new_password gated by the same
 *  StrongPassword rules as registration; no current password (the emailed
 *  token is the proof of identity). */
export interface ResetPasswordTokenPayload {
  token: string
  new_password: string
}
