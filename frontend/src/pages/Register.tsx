import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Message from '../components/Message'
import { message as toMessage } from '../train'

export default function Register() {
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setMessage('')
    setBusy(true)
    try {
      // The response is deliberately generic — identical whether the email was
      // free or already registered, so it can't be used to probe for accounts.
      // Display it as-is; there is no success/failure signal to branch on.
      const res = await api<{ message: string }>('/auth/register', {
        body: { username, email, password, confirm_password: confirmPassword },
      })
      setMessage(res.message)
    } catch (err) {
      setError(toMessage(err, 'Registration failed'))
    } finally {
      setBusy(false)
    }
  }

  if (message) {
    return (
      <div className="container-form">
        <div className="card">
          <h1 className="card__title">Check your email</h1>
          <Message kind="ok">{message}</Message>
        </div>
        <p className="auth-links">
          <Link to="/login">Log in</Link>
        </p>
      </div>
    )
  }

  return (
    <div className="container-form">
      <div className="card">
        <h1 className="card__title">Register</h1>
        <form onSubmit={onSubmit}>
          <div className="field">
            <label htmlFor="username">Username</label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              minLength={3}
              pattern="[a-zA-Z0-9_]+"
              title="Letters, numbers and underscores only"
              required
            />
            <small className="field__hint">
              At least 3 characters. Letters, numbers and underscores only.
            </small>
          </div>
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
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              minLength={8}
              maxLength={30}
              required
            />
            <small className="field__hint">
              8-30 characters, at least one uppercase letter and one digit.
            </small>
          </div>
          <div className="field">
            <label htmlFor="confirm-password">Confirm password</label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>
          <div className="form-actions">
            <button type="submit" className="btn-primary" disabled={busy}>
              {busy ? 'Registering...' : 'Register'}
            </button>
          </div>
        </form>
        {error && <Message kind="error">{error}</Message>}
        <p className="card__note">
          By registering you agree to our{' '}
          <Link to="/terms">Terms of Service</Link> and to how we handle your
          data, described in our <Link to="/privacy">Privacy Policy</Link>.
        </p>
      </div>
      <p className="auth-links">
        <Link to="/login">Log in</Link>
      </p>
    </div>
  )
}
