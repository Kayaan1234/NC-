import { Link, Navigate, useLocation } from 'react-router-dom'

export default function AccountDeleted() {
  const location = useLocation()
  // Reached only via the delete flow's navigate(state). A direct visit (or a
  // refresh, which drops router state) has nothing to show — send it home.
  const fromDelete = (location.state as { fromDelete?: boolean } | null)?.fromDelete

  if (!fromDelete) return <Navigate to="/" replace />

  return (
    <div className="auth-page">
      <div className="auth-card card narrow-card">
        <p className="eyebrow mono">account deleted</p>
        <h1>Sad to see you go.</h1>
        <p className="lede">
          Your account and all associated data have been permanently deleted. Thanks for trying
          NC++ — you're always welcome back.
        </p>
        <div className="stack-actions">
          <Link to="/" className="btn btn-primary full">
            Back to home
          </Link>
        </div>
      </div>
    </div>
  )
}
