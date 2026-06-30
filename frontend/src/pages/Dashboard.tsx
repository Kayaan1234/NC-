import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Dashboard() {
  const { user } = useAuth()
  if (!user) return null

  return (
    <div className="dash">
      <p className="eyebrow mono">authenticated session</p>
      <h1>
        Welcome, <span className="grad-fwd">{user.username}</span>.
      </h1>
      <p className="lede">
        You’re logged in. This page is gated behind a Bearer access token and resolved
        against <code>/users/me</code>.
      </p>

      <div className="dash-grid">
        <div className="card dash-field">
          <span className="dash-label mono">username</span>
          <span className="dash-value">{user.username}</span>
        </div>
        <div className="card dash-field">
          <span className="dash-label mono">email</span>
          <span className="dash-value">{user.email}</span>
        </div>
        <div className="card dash-field">
          <span className="dash-label mono">verified</span>
          <span className="dash-value">
            <span className={user.verified ? 'pill pill-ok' : 'pill pill-warn'}>
              {user.verified ? 'verified' : 'unverified'}
            </span>
          </span>
        </div>
        <div className="card dash-field">
          <span className="dash-label mono">user id</span>
          <span className="dash-value mono small">{user.id}</span>
        </div>
      </div>

      <p className="auth-alt dash-account-link">
        Manage your account in <Link to="/account">account settings</Link>.
      </p>
    </div>
  )
}
