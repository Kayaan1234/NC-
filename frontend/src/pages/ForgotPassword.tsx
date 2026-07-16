import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      // Generic by design: the same message comes back whether or not the
      // address is registered.
      const res = await api<{ message: string }>('/auth/forgot-password', { body: { email } })
      setMessage(res.message)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div>
      <h1>Forgot password</h1>
      {message ? (
        <p>{message}</p>
      ) : (
        <form onSubmit={onSubmit}>
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
          <button type="submit" disabled={busy}>
            {busy ? 'Sending...' : 'Send reset link'}
          </button>
        </form>
      )}
      {error && <p>{error}</p>}
      <p>
        <Link to="/login">Log in</Link>
      </p>
    </div>
  )
}
