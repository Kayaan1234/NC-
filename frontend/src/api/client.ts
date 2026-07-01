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

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

/** Thrown on any non-2xx response; `message` is the backend's `detail` string.
 *  `retryAfter` (seconds) is set on 429s when the backend's `Retry-After` header
 *  is readable — used to render a precise cooldown countdown. NOTE: because the
 *  frontend and API are cross-origin, this header is only exposed to JS once the
 *  backend's CORSMiddleware sets `expose_headers=["Retry-After"]`; until then it
 *  stays undefined and the UI falls back to the (already human-readable) message. */
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

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
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
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Could not reach the server. Is the backend running?')
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
    throw new ApiError(res.status, extractDetail(data, res.status), parseRetryAfter(res))
  }
  return data as T
}

/** Backend sets `Retry-After` to an integer-seconds string on its 429s. Only
 *  readable cross-origin once the API opts the header into CORS exposure. */
function parseRetryAfter(res: Response): number | undefined {
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

  logout: (refresh_token: string) =>
    request<void>('/auth/logout', { method: 'POST', body: { refresh_token }, auth: true }),

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
