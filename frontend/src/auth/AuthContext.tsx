import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api, refreshAccessToken, setOnAuthFailure } from '../api/client'
import { tokenStore } from '../api/tokenStore'
import type { LoginPayload, RegisterPayload, User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean // true during the initial "do we have a valid session?" check
  // Resolve to the logged-in user so callers can route by `verified`.
  login: (payload: LoginPayload) => Promise<User>
  // Does NOT log in or return a user: /auth/register replies with a generic
  // message that's identical whether the email was free or already taken, so we
  // must not auto-login (success vs. failure would re-expose which case it was).
  // Callers route to a neutral "check your email" screen instead.
  register: (payload: RegisterPayload) => Promise<void>
  logout: () => Promise<void>
  // Drop the local session without a server round-trip. For flows where the
  // server already invalidated the session: account deletion (the user row is
  // gone) and password reset (all refresh tokens revoked server-side).
  clearSession: () => void
  // Re-pull /users/me into state. Endpoints that mutate the user but return only
  // a message (verify, email change) leave `verified`/`email` stale otherwise.
  refreshUser: () => Promise<User | null>
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // On mount, re-establish the session. The access token lived only in memory, so
  // a page reload wiped it — re-mint it from the httpOnly refresh cookie (the
  // browser attaches it automatically). No/expired cookie => refresh returns
  // false and we stay logged out. Calls refreshAccessToken() directly, NOT via
  // request(), so a logged-out visitor never trips the onAuthFailure path below.
  useEffect(() => {
    let active = true
    // Register before any authed request can fire, so a mid-session refresh
    // failure (or a refreshed-but-still-rejected token) drops the UI to logged-out.
    setOnAuthFailure(() => {
      tokenStore.clear()
      setUser(null)
    })
    async function bootstrap() {
      try {
        const refreshed = await refreshAccessToken()
        if (refreshed && active) {
          const me = await api.me()
          if (active) setUser(me)
        }
      } catch {
        // Refreshed but /users/me still failed — treat as logged out.
        if (active) {
          tokenStore.clear()
          setUser(null)
        }
      } finally {
        if (active) setLoading(false)
      }
    }
    bootstrap()
    return () => {
      active = false
      setOnAuthFailure(null)
    }
  }, [])

  const login = useCallback(async (payload: LoginPayload) => {
    const tokens = await api.login(payload)
    // Refresh token is set as an httpOnly cookie by the backend; we only keep
    // the access token client-side.
    tokenStore.set(tokens.access_token)
    const me = await api.me()
    setUser(me)
    return me
  }, [])

  // Register only. We deliberately do NOT auto-login: the backend's response is
  // generic (no enumeration), so a follow-up login would succeed for a new email
  // but fail for an already-registered one — re-leaking the distinction and
  // logging a legitimate re-registrant into a confusing error. The caller sends
  // the user to a neutral "check your email" screen; they log in after verifying.
  const register = useCallback(async (payload: RegisterPayload) => {
    await api.register(payload)
  }, [])

  const refreshUser = useCallback(async () => {
    try {
      const me = await api.me()
      setUser(me)
      return me
    } catch {
      // Token gone/invalid — treat as logged out.
      tokenStore.clear()
      setUser(null)
      return null
    }
  }, [])

  const clearSession = useCallback(() => {
    tokenStore.clear()
    setUser(null)
  }, [])

  const logout = useCallback(async () => {
    try {
      // Cookie-authenticated: revokes the refresh token and clears the cookie
      // server-side. No token to pass — the httpOnly cookie rides along.
      await api.logout()
    } catch {
      // Best-effort server-side revocation; clear locally regardless.
    }
    tokenStore.clear()
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout, clearSession, refreshUser }}>
      {children}
    </AuthContext.Provider>
  )
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}
