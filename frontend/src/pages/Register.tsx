import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { ApiError } from '../api/client'
import { useCountdown, formatCountdown } from '../auth/useCountdown'

// Mirrors backend/schemas/auth.py validation so we fail fast, client-side.
function validate(fields: {
  username: string
  email: string
  password: string
  confirm: string
}): string | null {
  const { username, email, password, confirm } = fields
  if (!/^[a-zA-Z0-9_]+$/.test(username) || username.length < 3) {
    return 'Username must be ≥3 chars: letters, numbers, underscore only.'
  }
  if (!email.includes('@')) return 'Enter a valid email address.'
  if (password.length < 8 || password.length > 30) {
    return 'Password must be 8–30 characters.'
  }
  if (!/[A-Z]/.test(password)) return 'Password needs at least one uppercase letter.'
  if (!/[0-9]/.test(password)) return 'Password needs at least one digit.'
  if (password !== confirm) return 'Passwords do not match.'
  return null
}

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { remaining, start } = useCountdown()

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const localError = validate({ username, email, password, confirm })
    if (localError) {
      setError(localError)
      return
    }
    setError(null)
    setBusy(true)
    try {
      await register({
        username,
        email,
        password,
        confirm_password: confirm,
      })
      // No auto-login (the register response is deliberately generic), so route
      // to a neutral "check your email" screen — identical whether the address
      // was new or already registered.
      navigate('/registered', { state: { fromRegister: true, email } })
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
        // Rate limited (register fires a verification email): lock for the
        // exact backend cooldown so the button can't be hammered.
        if (err.status === 429 && err.retryAfter) start(err.retryAfter)
      } else {
        setError('Something went wrong')
      }
    } finally {
      setBusy(false)
    }
  }

  const locked = remaining > 0

  return (
    <div className="auth-page">
      <div className="auth-card card">
        <p className="eyebrow mono">join the build</p>
        <h1>Create account</h1>
        {error && <div className="alert alert-error">{error}</div>}
        <form onSubmit={onSubmit} noValidate>
          <div className="field">
            <label htmlFor="username">username</label>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
            />
            <span className="hint">≥3 chars · letters, numbers, underscore</span>
          </div>
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
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <span className="hint">8–30 chars · 1 uppercase · 1 digit</span>
          </div>
          <div className="field">
            <label htmlFor="confirm">confirm password</label>
            <input
              id="confirm"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </div>
          <button className="btn btn-primary full" type="submit" disabled={busy || locked}>
            {busy
              ? 'creating…'
              : locked
                ? `Try again in ${formatCountdown(remaining)}`
                : 'Create account'}
          </button>
        </form>
        <p className="auth-alt">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  )
}
