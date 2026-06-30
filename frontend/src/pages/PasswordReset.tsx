import { useEffect, useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

const REDIRECT_FROM = 3 // seconds; counts 3 -> 2 -> 1 then routes to login

export default function PasswordReset() {
  const location = useLocation()
  const navigate = useNavigate()
  const [count, setCount] = useState(REDIRECT_FROM)

  // Reached only via the reset flow's navigate(state). A direct visit has no
  // such state and nothing to confirm, so send those to login.
  const fromReset = (location.state as { fromReset?: boolean } | null)?.fromReset

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
          Your password has been updated and you've been signed out everywhere. Use your new
          password to log back in.
        </p>
        <p className="callout mono">Redirecting to login in {count}…</p>
      </div>
    </div>
  )
}
