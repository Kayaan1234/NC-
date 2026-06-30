import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { useCountdown, formatCountdown } from '../auth/useCountdown'
import { VERIFICATION_TTL_HOURS, RESEND_COOLDOWN_MINUTES } from '../authConfig'

export default function VerifyRequired() {
  const { user, refreshUser } = useAuth()
  const navigate = useNavigate()
  const [sent, setSent] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [checking, setChecking] = useState(false)
  const [stillUnverified, setStillUnverified] = useState(false)
  const { remaining, start } = useCountdown()

  async function onResend() {
    setError(null)
    setSent(false)
    setBusy(true)
    try {
      await api.resendVerification()
      setSent(true)
      // Lock the button for the known cooldown so the user doesn't hammer a 429.
      start(RESEND_COOLDOWN_MINUTES * 60)
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
        // Precise lockout when the API exposes Retry-After; else the message
        // ("sent recently, please wait") already tells the user to hold off.
        if (err.status === 429 && err.retryAfter) start(err.retryAfter)
      } else {
        setError('Something went wrong')
      }
    } finally {
      setBusy(false)
    }
  }

  // The user may have clicked the link in another tab/device. Let them re-check
  // without logging out and back in; if verified, send them to the dashboard.
  async function onCheck() {
    setChecking(true)
    setStillUnverified(false)
    try {
      const me = await refreshUser()
      if (me?.verified) navigate('/dashboard')
      else setStillUnverified(true)
    } finally {
      setChecking(false)
    }
  }

  const locked = remaining > 0

  return (
    <div className="auth-page">
      <div className="auth-card card narrow-card">
        <p className="eyebrow mono">one step left</p>
        <h1>
          Verify your <span className="grad-bwd">email</span>
        </h1>
        <p className="lede">
          Your dashboard unlocks once your email is confirmed. We sent a verification link to:
        </p>
        <p className="callout mono">{user?.email}</p>

        {sent && (
          <div className="alert alert-ok">
            Verification email sent. Check your inbox — the link is valid for {VERIFICATION_TTL_HOURS}{' '}
            hours.
          </div>
        )}
        {stillUnverified && (
          <div className="alert alert-warn">
            Still unverified. Click the link in the latest email, then refresh again.
          </div>
        )}
        {error && <div className="alert alert-error">{error}</div>}

        <div className="stack-actions">
          <button className="btn btn-primary full" onClick={onResend} disabled={busy || locked}>
            {busy ? 'sending…' : locked ? `Resend in ${formatCountdown(remaining)}` : 'Resend verification email'}
          </button>
          <button className="btn btn-ghost full" onClick={onCheck} disabled={checking}>
            {checking ? 'checking…' : "I've verified — refresh"}
          </button>
        </div>

        <p className="hint resend-note">
          You can request a new link every {RESEND_COOLDOWN_MINUTES} minutes. Each new link expires
          in {VERIFICATION_TTL_HOURS} hours and invalidates any previous one.
        </p>

        <p className="auth-alt">
          Wrong address? <Link to="/account">Update your email</Link>
        </p>
      </div>
    </div>
  )
}
