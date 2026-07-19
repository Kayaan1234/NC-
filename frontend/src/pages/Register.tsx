import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

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
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setBusy(false)
    }
  }

  if (message) {
    return (
      <div>
        <h1>Register</h1>
        <p>{message}</p>
        <p>
          <Link to="/login">Log in</Link>
        </p>
      </div>
    )
  }

  return (
    <div>
      <h1>Register</h1>
      <form onSubmit={onSubmit}>
        <div>
          <label htmlFor="username">Username</label>
          <br />
          <input
            id="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            minLength={3}
            pattern="[a-zA-Z0-9_]+"
            title="Letters, numbers and underscores only"
            required
          />
        </div>
        <div>
          <label htmlFor="email">Email</label>
          <br />
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div>
          <label htmlFor="password">Password</label>
          <br />
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            maxLength={30}
            required
          />
          <br />
          <small>8-30 characters, at least one uppercase letter and one digit.</small>
        </div>
        <div>
          <label htmlFor="confirm-password">Confirm password</label>
          <br />
          <input
            id="confirm-password"
            type="password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
          />
        </div>
        <button type="submit" disabled={busy}>
          {busy ? 'Registering...' : 'Register'}
        </button>
      </form>
      {error && <p>{error}</p>}
      <p>
        <small>
          By registering you agree to how we handle your data, described in our{' '}
          <Link to="/privacy">Privacy Policy</Link>.
        </small>
      </p>
      <p>
        <Link to="/login">Log in</Link>
      </p>
    </div>
  )
}
