import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { VERIFICATION_TTL_HOURS } from '../authConfig'

type Status = 'verifying' | 'success' | 'error' | 'no-token'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const { user, refreshUser } = useAuth()
  const [status, setStatus] = useState<Status>(token ? 'verifying' : 'no-token')
  const [error, setError] = useState<string | null>(null)
  // The token is single-use; the backend marks it consumed on first success.
  // React StrictMode (and any double render) would fire the effect twice, and
  // the second POST would see a used token and surface a *successful* verify as
  // an "invalid link" error. Latch so we POST exactly once.
  const fired = useRef(false)

  useEffect(() => {
    if (!token || fired.current) return
    fired.current = true
    ;(async () => {
      try {
        await api.verifyEmail(token)
        // If this browser has a session, pull the now-verified user into state
        // so the dashboard unlocks without a reload.
        await refreshUser()
        setStatus('success')
      } catch (err) {
        setError(err instanceof ApiError ? err.message : 'Something went wrong')
        setStatus('error')
      }
    })()
  }, [token, refreshUser])

  return (
    <div className="auth-page">
      <div className="auth-card card narrow-card">
        <p className="eyebrow mono">email verification</p>

        {status === 'verifying' && (
          <>
            <h1>Verifying…</h1>
            <p className="lede">Confirming your verification link.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <h1>
              You're <span className="grad-fwd">verified</span>.
            </h1>
            <p className="lede">Your email address is confirmed. Your account is good to go.</p>
            <div className="stack-actions">
              {user ? (
                <Link to="/dashboard" className="btn btn-primary full">
                  Go to dashboard
                </Link>
              ) : (
                <Link to="/login" className="btn btn-primary full">
                  Log in
                </Link>
              )}
            </div>
          </>
        )}

        {status === 'error' && (
          <>
            <h1>Link didn't work</h1>
            <div className="alert alert-error">{error}</div>
            <p className="lede">
              Verification links expire {VERIFICATION_TTL_HOURS} hours after they're sent, and each
              one can only be used once. Log in and request a fresh link from the verification
              screen.
            </p>
            <div className="stack-actions">
              <Link to="/login" className="btn btn-primary full">
                Log in to resend
              </Link>
            </div>
          </>
        )}

        {status === 'no-token' && (
          <>
            <h1>Missing token</h1>
            <p className="lede">
              This page needs a verification token from your email link. Open the most recent
              “Verify your email” message and click the button inside it.
            </p>
            <div className="stack-actions">
              <Link to="/login" className="btn btn-primary full">
                Log in
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
