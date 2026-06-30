import { createContext, useCallback, useContext, useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import { tokenStore } from '../api/tokenStore'
import type { LoginPayload, RegisterPayload, User } from '../api/types'

interface AuthState {
  user: User | null
  loading: boolean // true during the initial "do we have a valid session?" check
  // Resolve to the logged-in user so callers can route by `verified`.
  login: (payload: LoginPayload) => Promise<User>
  register: (payload: RegisterPayload) => Promise<User>
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

  // On mount, if we have a stored access token, try to resolve the session.
  useEffect(() => {
    let active = true
    async function bootstrap() {
      if (!tokenStore.getAccess()) {
        setLoading(false)
        return
      }
      try {
        const me = await api.me()
        if (active) setUser(me)
      } catch {
        // Token missing/expired/invalid — clear it and stay logged out.
        tokenStore.clear()
      } finally {
        if (active) setLoading(false)
      }
    }
    bootstrap()
    return () => {
      active = false
    }
  }, [])

  const login = useCallback(async (payload: LoginPayload) => {
    const tokens = await api.login(payload)
    tokenStore.set(tokens.access_token, tokens.refresh_token)
    const me = await api.me()
    setUser(me)
    return me
  }, [])

  // Backend /auth/register issues NO tokens, so we auto-login afterwards to
  // give the user an authenticated session in one step. The new account is
  // unverified, so callers route it to the verification gate.
  const register = useCallback(async (payload: RegisterPayload) => {
    await api.register(payload)
    const tokens = await api.login({ email: payload.email, password: payload.password })
    tokenStore.set(tokens.access_token, tokens.refresh_token)
    const me = await api.me()
    setUser(me)
    return me
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
    const refresh = tokenStore.getRefresh()
    if (refresh) {
      try {
        await api.logout(refresh)
      } catch {
        // Best-effort server-side revocation; clear locally regardless.
      }
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
