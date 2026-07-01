import { useEffect, useState } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { passwordError } from '../auth/passwordPolicy'

const REDIRECT_FROM = 3 // seconds; counts 3 -> 2 -> 1 then routes to login

// This one route serves two arrivals that both end on the same "all set" screen:
//   - the emailed forgot-password link  (?token=…)  -> validate, then the form
//   - the logged-in Account change flow (state.fromReset) -> straight to done
// A visit with neither has nothing to act on and is bounced to login.
//
// 'invalid' is reserved for a token the backend actually rejected (HTTP 400).
// 'unreachable' is for a validation attempt that failed for any OTHER reason
// (network down, CORS, 5xx) — we must NOT call a possibly-good link "expired"
// there, or the user discards it and burns a fresh one for nothing.
type Phase = 'validating' | 'invalid' | 'unreachable' | 'form' | 'done'

export default function PasswordReset() {
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useNavigate()
  const { clearSession } = useAuth()

  const token = searchParams.get('token')
  const fromReset = (location.state as { fromReset?: boolean } | null)?.fromReset

  // fromReset means the reset already happened (Account posted it) -> 'done'.
  // A token means we must first check it's still live before showing the form.
  const initialPhase: Phase | 'redirect' = fromReset ? 'done' : token ? 'validating' : 'redirect'
  const [phase, setPhase] = useState<Phase | 'redirect'>(initialPhase)
  const [count, setCount] = useState(REDIRECT_FROM)

  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // On landing with a token, ask the backend (read-only, non-consuming) whether
  // it's still valid, so we show 'link expired' vs. the form up front — before
  // the user types anything. A 400 is the expired/used/invalid case.
  useEffect(() => {
    if (initialPhase !== 'validating' || !token) return
    let cancelled = false
    api
      .validateResetToken(token)
      .then(() => !cancelled && setPhase('form'))
      .catch((err) => {
        if (cancelled) return
        // Only a real 400 means the token is bad/expired/used. Anything else
        // (unreachable server, CORS, 5xx) is our problem, not the link's.
        setPhase(err instanceof ApiError && err.status === 400 ? 'invalid' : 'unreachable')
      })
    return () => {
      cancelled = true
    }
  }, [initialPhase, token])

  // Both success arrivals land on 'done'. The reset revoked every refresh token
  // server-side, so any local session is already dead — drop it here, on this
  // PUBLIC page. (For the forgot flow there's usually no session at all; this is
  // a harmless no-op then.) Clearing it earlier, while a protected route was
  // still mounted, would have tripped that route's guard to /login first.
  useEffect(() => {
    if (phase === 'done') clearSession()
  }, [phase, clearSession])

  // Countdown runs for EITHER success path — keyed on 'done', not fromReset, so
  // the token flow gets the same auto-redirect the Account flow does.
  useEffect(() => {
    if (phase !== 'done') return
    if (count <= 0) {
      navigate('/login', { replace: true })
      return
    }
    const id = setTimeout(() => setCount((c) => c - 1), 1000)
    return () => clearTimeout(id)
  }, [phase, count, navigate])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!token) return
    const localError = passwordError(newPassword)
    if (localError) {
      setError(localError)
      return
    }
    if (newPassword !== confirm) {
      setError('Passwords do not match.')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await api.resetPasswordWithToken({ token, new_password: newPassword })
      setPhase('done')
    } catch (err) {
      // A 400 means the token expired or was consumed between load and submit —
      // there's no retrying the form, so swap to the 'link expired' screen. Any
      // other error (network, 422) is transient/fixable, so keep the form.
      if (err instanceof ApiError && err.status === 400) {
        setPhase('invalid')
      } else {
        setError(err instanceof ApiError ? err.message : 'Something went wrong')
        setBusy(false)
      }
    }
  }

  if (phase === 'redirect') return <Navigate to="/login" replace />

  if (phase === 'validating') {
    return (
      <div className="auth-page">
        <div className="auth-card card narrow-card">
          <p className="eyebrow mono">one moment</p>
          <h1>Checking your link…</h1>
          <p className="lede">Hang tight while we verify your reset link.</p>
        </div>
      </div>
    )
  }

  if (phase === 'unreachable') {
    return (
      <div className="auth-page">
        <div className="auth-card card narrow-card">
          <p className="eyebrow mono">hmm</p>
          <h1>Couldn't check your link.</h1>
          <p className="lede">
            We couldn't reach the server to verify your reset link. Your link may still be fine —
            check your connection and try again.
          </p>
          <button
            className="btn btn-primary full"
            type="button"
            onClick={() => window.location.reload()}
          >
            Try again
          </button>
          <p className="auth-alt">
            <Link to="/login">Back to login</Link>
          </p>
        </div>
      </div>
    )
  }

  if (phase === 'invalid') {
    return (
      <div className="auth-page">
        <div className="auth-card card narrow-card">
          <p className="eyebrow mono">link expired</p>
          <h1>
            This link has <span className="grad-fwd">expired</span>.
          </h1>
          <p className="lede">
            Password reset links are single-use and time-limited. Request a fresh one and we'll
            email you a new link.
          </p>
          <Link className="btn btn-primary full" to="/forgot-password">
            Request a new link
          </Link>
          <p className="auth-alt">
            <Link to="/login">Back to login</Link>
          </p>
        </div>
      </div>
    )
  }

  if (phase === 'done') {
    return (
      <div className="auth-page">
        <div className="auth-card card narrow-card">
          <p className="eyebrow mono">all set</p>
          <h1>
            Password <span className="grad-fwd">reset</span>.
          </h1>
          <p className="lede">
            You've successfully reset your password. For your security, you've been signed out
            everywhere and will log back in with your new password.
          </p>
          <p className="callout mono">Redirecting you to the login page in {count}…</p>
        </div>
      </div>
    )
  }

  // phase === 'form': the token checked out; collect and confirm the new password.
  return (
    <div className="auth-page">
      <div className="auth-card card">
        <p className="eyebrow mono">choose a new password</p>
        <h1>Set a new password</h1>
        <p className="lede">
          Pick a new password for your account. You'll use it to log back in once it's saved.
        </p>

        {error && <div className="alert alert-error">{error}</div>}

        <form onSubmit={onSubmit} noValidate>
          <div className="field">
            <label htmlFor="new-password">new password</label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              required
            />
            <span className="hint">8–30 chars · 1 uppercase · 1 digit</span>
          </div>
          <div className="field">
            <label htmlFor="confirm-password">confirm new password</label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </div>
          <button className="btn btn-primary full" type="submit" disabled={busy}>
            {busy ? 'saving…' : 'Reset password'}
          </button>
        </form>
      </div>
    </div>
  )
}
