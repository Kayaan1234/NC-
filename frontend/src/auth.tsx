import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { api, refreshSession, setAccessToken } from './api'
import type { User } from './api'

type AuthValue = {
  user: User | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  reload: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Every function here is referentially stable, and that is a contract rather
  // than a micro-optimisation: `reload` is read from this context into a
  // useEffect dependency array (VerifyEmail.tsx), so a fresh identity on each
  // render would re-fire that effect on every unrelated auth state change.
  const loadUser = useCallback(async () => {
    setUser(await api<User>('/users/me', { method: 'GET', auth: true }))
  }, [])

  // Session restore on mount: there's no readable token to check, so the only
  // way to know whether we're logged in is to ask the refresh cookie. A failure
  // here is the normal logged-out case, not an error worth showing.
  useEffect(() => {
    ;(async () => {
      try {
        if (await refreshSession()) await loadUser()
      } catch {
        setAccessToken(null)
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const login = useCallback(
    async (email: string, password: string) => {
      const session = await api<{ access_token: string }>('/auth/login', {
        body: { email, password },
      })
      setAccessToken(session.access_token)
      await loadUser()
    },
    [loadUser],
  )

  const logout = useCallback(async () => {
    // Authenticated by the refresh cookie, not the Bearer token, and idempotent
    // server-side — so this is worth attempting even if our token is stale. Drop
    // local state regardless of the outcome.
    try {
      await api<void>('/auth/logout')
    } finally {
      setAccessToken(null)
      setUser(null)
    }
  }, [])

  // Without this the object is new on every render, so every useAuth() consumer
  // re-renders whenever the provider does — which is the whole tree, since the
  // provider sits above the router.
  const value = useMemo(
    () => ({ user, loading, login, logout, reload: loadUser }),
    [user, loading, login, logout, loadUser],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
