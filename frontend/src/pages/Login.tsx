import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import Message from '../components/Message'
import { message } from '../train'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await login(email, password)
      navigate('/')
    } catch (err) {
      setError(message(err, 'Login failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container-form">
      <div className="card">
        <h1 className="card__title">Log in</h1>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="email">Email</label>
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
            <label htmlFor="password">Password</label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? 'Logging in...' : 'Log in'}
            </button>
          </div>
        </form>
        {error && <Message kind="error">{error}</Message>}
      </div>
      {/* The top bar carries no auth links (both targets are PublicOnly routes),
          so the two auth pages cross-link each other from here. */}
      <p className="auth-links">
        <Link to="/register">Register</Link>
        <Link to="/forgot-password">Forgot password</Link>
      </p>
    </div>
  )
}
