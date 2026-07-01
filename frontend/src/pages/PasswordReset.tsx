import { useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const REDIRECT_FROM = 3 // seconds; counts 3 -> 2 -> 1 then routes to login

export default function PasswordReset() {
  const location = useLocation()
  const navigate = useNavigate()
  const { clearSession } = useAuth()
  const [count, setCount] = useState(REDIRECT_FROM)

  // Reached only via the reset flow's navigate(state). A direct visit has no
  // such state and nothing to confirm, so send those to login.
  const fromReset = (location.state as { fromReset?: boolean } | null)?.fromReset

  // The reset revoked every refresh token server-side, so the local session is
  // already dead — drop it here, on this PUBLIC page, once the navigation has
  // landed. Clearing it back in the account form set user=null while the
  // protected /account route was still mounted, so its guard redirected to
  // /login before this confirmation page could ever render.
  useEffect(() => {
    if (fromReset) clearSession()
  }, [fromReset, clearSession])

  useEffect(() => {
    if (!fromReset) return
    if (count <= 0) {
      navigate('/login', { replace: true })
      return
    }
    const id = setTimeout(() => setCount((c) => c - 1), 1000)
    return () => clearTimeout(id)
  }, [count, fromReset, navigate])

  if (!fromReset) return <Navigate to="/login" replace />

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
