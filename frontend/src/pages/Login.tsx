import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../api/client'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      const me = await login({ email, password })
      navigate(me.verified ? '/dashboard' : '/verify-required')
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card card">
        <p className="eyebrow mono">welcome back</p>
        <h1>Log in</h1>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={onSubmit} noValidate>
          <div className="field">
            <label htmlFor="email">email</label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>
          <div className="field">
            <label htmlFor="password">password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <button className="btn btn-primary full" type="submit" disabled={busy}>
            {busy ? 'logging in…' : 'Log in'}
          </button>
        </form>
        <p className="auth-alt">
          <Link to="/forgot-password">Forgot your password?</Link>
        </p>
        <p className="auth-alt">
          No account? <Link to="/register">Create one</Link>
        </p>
      </div>
    </div>
  )
}
