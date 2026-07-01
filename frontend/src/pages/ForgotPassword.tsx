import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { RESET_TTL_HOURS } from '../authConfig'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  // Once submitted we swap the form for a generic confirmation. We intentionally
  // show the SAME message whether or not the address is registered — the backend
  // reveals nothing (anti-enumeration), so the UI mustn't leak it either.
  const [sent, setSent] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.forgotPassword({ email })
      setSent(true)
    } catch (err) {
      // A network error is the only thing worth surfacing; a 200 with an unknown
      // email still resolves, so we never end up here for "email not found".
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  if (sent) {
    return (
      <div className="auth-page">
        <div className="auth-card card narrow-card">
          <p className="eyebrow mono">check your inbox</p>
          <h1>
            Link <span className="grad-fwd">sent</span>.
          </h1>
          <p className="lede">
            If <strong>{email}</strong> matches an account, we've emailed a link to reset your
            password. It expires in {RESET_TTL_HOURS === 1 ? 'an hour' : `${RESET_TTL_HOURS} hours`}.
          </p>
          <p className="hint resend-note">
            Didn't get it? Check your spam folder, or{' '}
            <button className="linklike" type="button" onClick={() => setSent(false)}>
              try a different email
            </button>
            .
          </p>
          <p className="auth-alt">
            <Link to="/login">Back to login</Link>
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="auth-page">
      <div className="auth-card card">
        <p className="eyebrow mono">forgot password</p>
        <h1>Reset your password</h1>
        <p className="lede">
          Enter the email on your account and we'll send you a link to choose a new password.
        </p>

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
          <button className="btn btn-primary full" type="submit" disabled={busy}>
            {busy ? 'sending…' : 'Send reset link'}
          </button>
        </form>

        <p className="auth-alt">
          Remembered it? <Link to="/login">Back to login</Link>
        </p>
      </div>
    </div>
  )
}
