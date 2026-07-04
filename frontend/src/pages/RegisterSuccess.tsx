import { Link, Navigate, useLocation } from 'react-router-dom'

export default function RegisterSuccess() {
  const location = useLocation()
  // Reached only via the register flow's navigate(state). A direct visit (or a
  // refresh, which drops router state) has nothing to confirm — send it home.
  const state = location.state as { fromRegister?: boolean; email?: string } | null
  if (!state?.fromRegister) return <Navigate to="/" replace />

  return (
    <div className="auth-page">
      <div className="auth-card card narrow-card">
        <p className="eyebrow mono">check your inbox</p>
        <h1>Almost there.</h1>
        <p className="lede">
          {state.email ? (
            <>
              We've sent an email to <strong>{state.email}</strong>.{' '}
            </>
          ) : (
            "We've sent you an email. "
          )}
          {/* Deliberately generic — covers BOTH the new-account and
              already-registered cases without revealing which one applies, so
              the page can't be used to enumerate accounts either. */}
          If those details are available, it contains a link to verify your new
          account. Already registered with this email? We've sent a sign-in
          reminder instead — either way, head to your inbox to continue.
        </p>
        <div className="stack-actions">
          <Link to="/login" className="btn btn-primary full">
            Go to login
          </Link>
        </div>
      </div>
    </div>
  )
}
