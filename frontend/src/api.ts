// The access token lives in memory only. The refresh token is delivered solely
// as an httpOnly cookie scoped to /auth, so JS can neither read nor persist it —
// restoring a session after a reload means calling /auth/refresh, not reading
// storage. Deliberately nothing here touches localStorage.

let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

export class ApiError extends Error {
  status: number
  retryAfter?: number

  constructor(status: number, message: string, retryAfter?: number) {
    super(message)
    this.status = status
    this.retryAfter = retryAfter
  }
}

/** The body /auth/login and /auth/refresh both return. */
export type Session = {
  access_token: string
  user_id: string
  verified: boolean
}

export type User = {
  id: string
  username: string
  email: string
  verified: boolean
}

type Options = {
  method?: string
  body?: unknown
  auth?: boolean
}

async function send(path: string, options: Options): Promise<Response> {
  const headers: Record<string, string> = {}
  if (options.body !== undefined) headers['Content-Type'] = 'application/json'
  if (options.auth && accessToken) headers['Authorization'] = `Bearer ${accessToken}`

  return fetch(path, {
    method: options.method ?? 'POST',
    headers,
    // Required. Without it the browser neither stores the refresh cookie from
    // login nor sends it back to /auth/refresh — refresh and logout would fail
    // with no visible cause.
    credentials: 'include',
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  })
}

async function errorFrom(res: Response): Promise<ApiError> {
  try {
    const body = await res.json()
    const detail = body?.detail
    if (typeof detail === 'string') return new ApiError(res.status, detail, body?.retry_after)
    // FastAPI validation errors: detail is a list of {loc, msg} entries.
    if (Array.isArray(detail)) {
      return new ApiError(res.status, detail.map((d) => d?.msg ?? 'Invalid input').join('; '))
    }
  } catch {
    // Non-JSON body; fall through to the generic message.
  }
  return new ApiError(res.status, `Request failed (${res.status})`)
}

let inFlightRefresh: Promise<Session | null> | null = null

/** Mint a new access token from the refresh cookie. Null means "not logged in". */
export async function refreshSession(): Promise<Session | null> {
  // Refresh ROTATES the token: it revokes the cookie it was given and issues a
  // new one. So two concurrent refreshes are a real hazard, not just waste — the
  // second sends the same cookie before the first response replaces it, and gets
  // a 401 for a token the first call just revoked. Share one in-flight call so
  // overlapping callers (StrictMode's double mount, parallel 401 retries) can't
  // race each other into a spurious logout.
  if (inFlightRefresh) return inFlightRefresh

  inFlightRefresh = (async () => {
    try {
      const res = await send('/auth/refresh', {})
      if (!res.ok) return null
      const session: Session = await res.json()
      accessToken = session.access_token
      return session
    } finally {
      inFlightRefresh = null
    }
  })()

  return inFlightRefresh
}

async function request(path: string, options: Options): Promise<Response> {
  let res = await send(path, options)

  // Access tokens expire in minutes while the refresh cookie lasts days, so a
  // 401 on an authenticated call usually just means "token aged out" — rotate
  // and retry once before surfacing it as a real failure.
  if (res.status === 401 && options.auth && path !== '/auth/refresh') {
    if (await refreshSession()) res = await send(path, options)
  }

  if (!res.ok) throw await errorFrom(res)
  return res
}

export async function api<T>(path: string, options: Options = {}): Promise<T> {
  const res = await request(path, options)
  if (res.status === 204) return undefined as T
  return res.json()
}

/**
 * Fetch an authenticated file and hand it to the browser's downloader.
 *
 * The report endpoint requires the Bearer token, which lives in memory only, so
 * a plain <a href> can't reach it — we fetch it (reusing the same refresh-retry
 * as any other call), then click a throwaway object URL. Prefers the filename the
 * server set in Content-Disposition, falling back to the caller's name.
 */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const res = await request(path, { method: 'GET', auth: true })
  const blob = await res.blob()

  const disposition = res.headers.get('Content-Disposition') ?? ''
  const match = /filename="?([^"]+)"?/.exec(disposition)
  const name = match ? match[1] : fallbackName

  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  URL.revokeObjectURL(url)
}
