import { tokenStore } from './tokenStore'
import type {
  DeleteAccountPayload,
  ForgotPasswordPayload,
  LoginPayload,
  MessageResponse,
  RegisterPayload,
  RegisterResponse,
  ResetPasswordPayload,
  ResetPasswordTokenPayload,
  TokenResponse,
  UpdateEmailPayload,
  User,
} from './types'

// Must be same-SITE with the SPA (localhost:5173) or the SameSite=Strict refresh
// cookie won't be sent — hence `localhost`, not `127.0.0.1` (different site).
const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

/** Thrown on any non-2xx response; `message` is the backend's `detail` string.
 *  `retryAfter` (seconds) is set on 429s and drives a precise cooldown countdown.
 *  The backend sends it two ways — a `retry_after` field in the JSON body and a
 *  `Retry-After` header — and we prefer the body since it's always readable,
 *  whereas the header is only exposed to cross-origin JS when the API sets
 *  `expose_headers=["Retry-After"]`. If neither is present the UI falls back to
 *  the (already human-readable) message. */
export class ApiError extends Error {
  status: number
  retryAfter?: number
  constructor(status: number, message: string, retryAfter?: number) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
    this.name = 'ApiError'
  }
}

interface RequestOptions {
  method?: string
  body?: unknown
  auth?: boolean // attach the Bearer access token
}

// --- Silent refresh --------------------------------------------------------
//
// The access token lives only in memory and expires quickly; the refresh token
// is an httpOnly cookie the browser attaches automatically. refreshAccessToken()
// trades that cookie for a fresh access token. A single in-flight promise is
// shared across all callers, so N requests 401ing at once — or a child component
// racing the mount bootstrap — trigger exactly ONE /auth/refresh, not N rotations
// against the same cookie (the backend rotates on refresh, so the 2nd would
// present an already-revoked token and fail).
let refreshInFlight: Promise<boolean> | null = null

export function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = doRefresh().finally(() => {
      refreshInFlight = null
    })
  }
  return refreshInFlight
}

async function doRefresh(): Promise<boolean> {
  // Raw fetch, NOT request(): the interceptor must never recurse into itself,
  // and a missing/expired cookie here is an expected "not logged in", not an
  // error to surface.
  try {
    const res = await fetch(`${BASE_URL}/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })
    if (!res.ok) return false
    const data = (await res.json()) as TokenResponse
    tokenStore.set(data.access_token)
    return true
  } catch {
    return false
  }
}

// Fired when a session is definitively dead — a mid-session refresh failed, or a
// freshly refreshed token is still rejected. AuthContext registers a handler that
// drops the app to logged-out; the client stays decoupled from React.
let onAuthFailure: (() => void) | null = null
export function setOnAuthFailure(handler: (() => void) | null): void {
  onAuthFailure = handler
}

async function request<T>(path: string, opts: RequestOptions = {}, retry = true): Promise<T> {
  const { method = 'GET', body, auth = false } = opts
  const headers: Record<string, string> = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (auth) {
    const token = tokenStore.getAccess()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  let res: Response
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      method,
      headers,
      // Send/receive the httpOnly refresh cookie: required so login stores it,
      // refresh/logout send it, and the revoke-all routes' clearing Set-Cookie
      // is honored. Works cross-origin because the API sets
      // Access-Control-Allow-Credentials with specific (non-*) origins.
      credentials: 'include',
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Could not reach the server. Is the backend running?')
  }

  // Access token expired mid-session: silently refresh once (the httpOnly cookie
  // rides along) and replay the original request — its headers are rebuilt below
  // from the now-rotated token. Gated on `auth` (only Bearer-carrying calls 401
  // on an expired access token) and `retry` so a replay that still 401s doesn't
  // loop.
  if (res.status === 401 && auth && retry) {
    const refreshed = await refreshAccessToken()
    if (refreshed) return request<T>(path, opts, false)
    // Refresh cookie gone/expired/revoked: the session is truly over.
    onAuthFailure?.()
  }

  if (res.status === 204) return undefined as T

  let data: unknown = null
  const text = await res.text()
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }

  if (!res.ok) {
    // A retried request that still 401s (fresh token, still rejected => account
    // deleted or all sessions revoked) is likewise a dead session.
    if (res.status === 401 && auth && !retry) onAuthFailure?.()
    throw new ApiError(res.status, extractDetail(data, res.status), parseRetryAfter(res, data))
  }
  return data as T
}

/** Seconds until a rate-limited action unlocks. Prefers the `retry_after` field
 *  in the JSON body (always readable) and falls back to the `Retry-After` header
 *  (only exposed cross-origin when the API opts it into CORS exposure). */
function parseRetryAfter(res: Response, data: unknown): number | undefined {
  if (data && typeof data === 'object' && 'retry_after' in data) {
    const secs = Number((data as { retry_after: unknown }).retry_after)
    if (Number.isFinite(secs)) return secs
  }
  const raw = res.headers.get('Retry-After')
  if (!raw) return undefined
  const secs = Number(raw)
  return Number.isFinite(secs) ? secs : undefined
}

/** FastAPI puts errors in `detail` — a string for HTTPException, or an array
 *  of `{loc, msg}` for 422 validation errors. Flatten both to one message. */
function extractDetail(data: unknown, status: number): string {
  if (data && typeof data === 'object' && 'detail' in data) {
    const detail = (data as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
      return detail
        .map((e) => (e && typeof e === 'object' && 'msg' in e ? String((e as { msg: unknown }).msg) : String(e)))
        .join('; ')
    }
  }
  return `Request failed (${status})`
}

export const api = {
  register: (payload: RegisterPayload) =>
    request<RegisterResponse>('/auth/register', { method: 'POST', body: payload }),

  login: (payload: LoginPayload) =>
    request<TokenResponse>('/auth/login', { method: 'POST', body: payload }),

  // Cookie-authenticated: the backend reads the httpOnly refresh cookie (no
  // Bearer needed), revokes that token, and clears the cookie. 204 on success.
  logout: () => request<void>('/auth/logout', { method: 'POST' }),

  me: () => request<User>('/users/me', { auth: true }),

  // Public: the token comes from the email link, the clicker may be logged out.
  verifyEmail: (token: string) =>
    request<MessageResponse>('/auth/verify', { method: 'POST', body: { token } }),

  resendVerification: () =>
    request<MessageResponse>('/auth/resend-verification', { method: 'POST', auth: true }),

  updateEmail: (payload: UpdateEmailPayload) =>
    request<MessageResponse>('/users/me/email', { method: 'PATCH', body: payload, auth: true }),

  // Reset password revokes ALL refresh tokens server-side (including this
  // session), so the caller should clear local tokens and route to login.
  resetPassword: (payload: ResetPasswordPayload) =>
    request<MessageResponse>('/users/me/password', { method: 'PATCH', body: payload, auth: true }),

  // 204 on success; the user row (and its tokens, via cascade) is gone.
  deleteAccount: (payload: DeleteAccountPayload) =>
    request<void>('/users/me', { method: 'DELETE', body: payload, auth: true }),

  // Public. Always resolves with the same generic message whether or not the
  // email is registered — the backend deliberately reveals nothing, so the UI
  // must not branch on it either (no email enumeration).
  forgotPassword: (payload: ForgotPasswordPayload) =>
    request<MessageResponse>('/auth/forgot-password', { method: 'POST', body: payload }),

  // Public, read-only. The reset landing page calls this on load to decide
  // between the 'link expired' screen and the form; it does NOT consume the
  // single-use token. Throws ApiError(400) on an invalid/expired/used token.
  validateResetToken: (token: string) =>
    request<MessageResponse>('/auth/reset-password/validate', { method: 'POST', body: { token } }),

  // Public. Consumes the emailed token, sets the new password, and revokes every
  // session server-side — so afterward route to login, don't auto-authenticate.
  resetPasswordWithToken: (payload: ResetPasswordTokenPayload) =>
    request<MessageResponse>('/auth/reset-password', { method: 'POST', body: payload }),
}
