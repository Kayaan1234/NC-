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

/** /auth/register returns ONLY a generic message — deliberately identical
 *  whether the email was free or already taken (no account enumeration), so no
 *  user_id/verified is exposed. The SPA ignores the body and auto-logs-in. */
export interface RegisterResponse {
  message: string
}

export interface User {
  id: string
  username: string
  email: string
  verified: boolean
}

/** One rung of the roadmap as the dashboard sees it. Mirrors
 *  backend/schemas/auth.py RungProgressOut. `status` is computed server-side
 *  from the user's progress; a "locked" rung with `exercises_total === 0` is a
 *  not-yet-authored "COMING SOON" placeholder (its `title` is literally that). */
export type RungStatus = 'locked' | 'unlocked' | 'completed'

export interface RungProgress {
  id: string
  number: number
  slug: string
  title: string
  status: RungStatus
  exercises_completed: number
  exercises_total: number
}

/** GET /users/me/dashboard — the roadmap feed. `current_rung_number` is the
 *  first unlocked-but-unfinished rung (where the learner should pick up), or
 *  null once nothing is in progress. */
export interface DashboardData {
  rungs: RungProgress[]
  current_rung_number: number | null
}

/** GET /rungs/{number}/exercises — one rung's exercises with this user's
 *  progress. Mirrors backend UserRungProgressResponse / ExerciseListItem. */
export type ExerciseProgressStatus = 'not_started' | 'in_progress' | 'completed'

export interface ExerciseListItem {
  id: string
  slug: string
  title: string
  order_index: number
  status: ExerciseProgressStatus
  read_only: boolean
}

export interface RungExercises {
  exercises: ExerciseListItem[]
  /** Slug of the first not-completed exercise (resume point), or null when the
   *  rung is empty or fully complete. */
  next_incomplete_slug: string | null
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
