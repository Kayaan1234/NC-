// api.ts — the fetch wrapper, the single-flight refresh, and the 401 retry.
//
// This module holds two pieces of mutable state at module scope: `accessToken`
// and `inFlightRefresh`. Only the first has an exported setter, so every test
// re-imports the module through `vi.resetModules()` and a dynamic import. That
// is not ceremony — a leaked in-flight promise would make later tests pass or
// fail depending on the order they ran in.

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

type Api = typeof import('./api')

/** A fresh copy of the module, with no state carried over from another test. */
async function freshApi(): Promise<Api> {
  vi.resetModules()
  return import('./api')
}

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json', ...headers },
  })
}

const SESSION = { access_token: 'new-token', user_id: 'u1', verified: true }

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn()
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

/** The options object api.ts passed to fetch on call `n`. */
const callOptions = (n: number) => fetchMock.mock.calls[n][1] as RequestInit

describe('send', () => {
  it('always sends credentials, without which the refresh cookie never rides along', async () => {
    // Load-bearing: without it the browser neither stores the cookie from login
    // nor returns it to /auth/refresh, and both fail with no visible cause.
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(200, {}))

    await api.api('/health', { method: 'GET' })

    expect(callOptions(0).credentials).toBe('include')
  })

  it('defaults to POST', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(200, {}))

    await api.api('/auth/logout')

    expect(callOptions(0).method).toBe('POST')
  })

  it('sets a JSON content type only when there is a body', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(200, {}))

    await api.api('/auth/login', { body: { email: 'a@b.com' } })
    expect((callOptions(0).headers as Record<string, string>)['Content-Type']).toBe(
      'application/json',
    )
    expect(callOptions(0).body).toBe('{"email":"a@b.com"}')

    await api.api('/health', { method: 'GET' })
    expect((callOptions(1).headers as Record<string, string>)['Content-Type']).toBeUndefined()
    expect(callOptions(1).body).toBeUndefined()
  })

  it('attaches the bearer token only when the call asks to be authenticated', async () => {
    const api = await freshApi()
    api.setAccessToken('abc123')
    fetchMock.mockImplementation(async () => jsonResponse(200, {}))

    await api.api('/users/me', { method: 'GET', auth: true })
    expect((callOptions(0).headers as Record<string, string>).Authorization).toBe('Bearer abc123')

    await api.api('/auth/login', { body: {} })
    expect((callOptions(1).headers as Record<string, string>).Authorization).toBeUndefined()
  })

  it('sends no authorization header when there is no token yet', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(200, {}))

    await api.api('/users/me', { method: 'GET', auth: true })

    expect((callOptions(0).headers as Record<string, string>).Authorization).toBeUndefined()
  })
})

describe('errorFrom', () => {
  it('uses a string detail as the message', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(400, { detail: 'Invalid email or password' }))

    await expect(api.api('/auth/login', { body: {} })).rejects.toMatchObject({
      status: 400,
      message: 'Invalid email or password',
    })
  })

  it('joins a FastAPI validation array into one sentence', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => 
      jsonResponse(422, {
        detail: [
          { loc: ['body', 'email'], msg: 'not a valid email address' },
          { loc: ['body', 'password'], msg: 'too short' },
        ],
      }),
    )

    await expect(api.api('/auth/register', { body: {} })).rejects.toThrow(
      'not a valid email address; too short',
    )
  })

  it('falls back for a validation entry with no message', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(422, { detail: [{ loc: ['body'] }] }))

    await expect(api.api('/auth/register', { body: {} })).rejects.toThrow('Invalid input')
  })

  it('falls back to a generic message for a non-JSON body', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => new Response('<html>502 Bad Gateway</html>', { status: 502 }))

    await expect(api.api('/health', { method: 'GET' })).rejects.toThrow('Request failed (502)')
  })

  it('carries retry_after off a 429 so the UI can show a countdown', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => 
      jsonResponse(429, { detail: 'Too many requests.', retry_after: 45 }),
    )

    await expect(api.api('/auth/login', { body: {} })).rejects.toMatchObject({
      status: 429,
      retryAfter: 45,
    })
  })
})

describe('refreshSession', () => {
  it('stores the new access token on success', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(200, SESSION))

    await expect(api.refreshSession()).resolves.toEqual(SESSION)
    expect(api.getAccessToken()).toBe('new-token')
  })

  it('returns null without throwing when there is no valid cookie', async () => {
    // The normal logged-out case, not an error: the app must render the landing
    // page, not an error screen.
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(401, { detail: 'Invalid or expired refresh token' }))

    await expect(api.refreshSession()).resolves.toBeNull()
    expect(api.getAccessToken()).toBeNull()
  })

  it('shares one in-flight call between concurrent callers', async () => {
    // The hazard is real, not just waste: refresh ROTATES the cookie, so a
    // second concurrent call sends a token the first one already revoked and
    // gets a 401 — a spurious logout. StrictMode's double mount hits this.
    const api = await freshApi()
    let release!: (r: Response) => void
    fetchMock.mockImplementation(() => new Promise<Response>((resolve) => (release = resolve)))

    const [a, b, c] = [api.refreshSession(), api.refreshSession(), api.refreshSession()]
    release(jsonResponse(200, SESSION))

    expect(await a).toEqual(SESSION)
    expect(await b).toEqual(SESSION)
    expect(await c).toEqual(SESSION)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('clears the in-flight slot so a later refresh really refreshes', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(200, SESSION))

    await api.refreshSession()
    await api.refreshSession()

    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('clears the in-flight slot even when the call rejects', async () => {
    // The finally block. Without it one network blip would wedge every future
    // refresh onto a permanently rejected promise.
    const api = await freshApi()
    fetchMock.mockRejectedValueOnce(new TypeError('network down'))

    await expect(api.refreshSession()).rejects.toThrow('network down')

    fetchMock.mockImplementation(async () => jsonResponse(200, SESSION))
    await expect(api.refreshSession()).resolves.toEqual(SESSION)
  })
})

describe('the 401 retry', () => {
  it('refreshes once and replays an authenticated call', async () => {
    // Access tokens expire in minutes while the refresh cookie lasts days, so a
    // 401 here usually just means "aged out".
    const api = await freshApi()
    api.setAccessToken('stale-token')
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Could not validate credentials' }))
      .mockResolvedValueOnce(jsonResponse(200, SESSION))
      .mockResolvedValueOnce(jsonResponse(200, { id: 'u1', username: 'alice' }))

    await expect(api.api('/users/me', { method: 'GET', auth: true })).resolves.toMatchObject({
      username: 'alice',
    })

    expect(fetchMock.mock.calls.map((c) => c[0])).toEqual([
      '/users/me',
      '/auth/refresh',
      '/users/me',
    ])
    // The replay carries the NEW token, not the stale one.
    expect((callOptions(2).headers as Record<string, string>).Authorization).toBe(
      'Bearer new-token',
    )
  })

  it('does not retry an unauthenticated call', async () => {
    // A 401 from /auth/login means bad credentials. Refreshing would be
    // pointless and would mask the real error.
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(401, { detail: 'Invalid email or password' }))

    await expect(api.api('/auth/login', { body: {} })).rejects.toThrow('Invalid email or password')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('does not retry the refresh endpoint itself, which would recurse', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(401, { detail: 'Invalid or expired refresh token' }))

    await expect(api.api('/auth/refresh', { auth: true })).rejects.toThrow()
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('surfaces the original error when the refresh also fails', async () => {
    // Must not loop, and must not swallow the failure into something vaguer.
    const api = await freshApi()
    api.setAccessToken('stale-token')
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Could not validate credentials' }))
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'Invalid or expired refresh token' }))

    await expect(api.api('/users/me', { method: 'GET', auth: true })).rejects.toThrow(
      'Could not validate credentials',
    )
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('retries at most once, so a persistently 401ing endpoint terminates', async () => {
    const api = await freshApi()
    api.setAccessToken('stale-token')
    fetchMock
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'nope' }))
      .mockResolvedValueOnce(jsonResponse(200, SESSION))
      .mockResolvedValueOnce(jsonResponse(401, { detail: 'still nope' }))

    await expect(api.api('/users/me', { method: 'GET', auth: true })).rejects.toThrow('still nope')
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('does not retry a non-401 failure', async () => {
    const api = await freshApi()
    api.setAccessToken('token')
    fetchMock.mockImplementation(async () => jsonResponse(403, { detail: 'Email address not verified' }))

    await expect(api.api('/train/models', { method: 'GET', auth: true })).rejects.toThrow(
      'Email address not verified',
    )
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})

describe('api', () => {
  it('returns undefined for 204 rather than trying to parse an empty body', async () => {
    // /auth/logout and DELETE /users/me both answer 204; res.json() would throw.
    const api = await freshApi()
    fetchMock.mockImplementation(async () => new Response(null, { status: 204 }))

    await expect(api.api('/auth/logout')).resolves.toBeUndefined()
  })

  it('parses a JSON body on success', async () => {
    const api = await freshApi()
    fetchMock.mockImplementation(async () => jsonResponse(200, { id: 'u1' }))

    await expect(api.api('/users/me', { method: 'GET' })).resolves.toEqual({ id: 'u1' })
  })
})

describe('the access token', () => {
  it('starts empty and is never written to storage', async () => {
    // Deliberate: the token lives in memory only, so a session cannot be
    // restored by reading storage — only by calling /auth/refresh.
    const api = await freshApi()
    expect(api.getAccessToken()).toBeNull()
    expect(typeof localStorage === 'undefined' || localStorage.length === 0).toBe(true)
  })

  it('can be cleared on logout', async () => {
    const api = await freshApi()
    api.setAccessToken('abc')
    api.setAccessToken(null)
    expect(api.getAccessToken()).toBeNull()
  })
})
