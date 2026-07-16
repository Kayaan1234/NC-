import { createContext, useContext, useEffect, useState } from 'react'
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

  async function loadUser() {
    setUser(await api<User>('/users/me', { method: 'GET', auth: true }))
  }

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

  async function login(email: string, password: string) {
    const session = await api<{ access_token: string }>('/auth/login', {
      body: { email, password },
    })
    setAccessToken(session.access_token)
    await loadUser()
  }

  async function logout() {
    // Authenticated by the refresh cookie, not the Bearer token, and idempotent
    // server-side — so this is worth attempting even if our token is stale. Drop
    // local state regardless of the outcome.
    try {
      await api<void>('/auth/logout')
    } finally {
      setAccessToken(null)
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, reload: loadUser }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
