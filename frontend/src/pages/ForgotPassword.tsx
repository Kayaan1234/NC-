import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import Message from '../components/Message'
import { message as toMessage } from '../train'

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
      setError(toMessage(err, 'Request failed'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container-form">
      <div className="card">
        <h1 className="card__title">Forgot password</h1>
        {message ? (
          <Message kind="ok">{message}</Message>
        ) : (
          <>
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
              <div className="form-actions">
                <button type="submit" className="btn-primary" disabled={busy}>
                  {busy ? 'Sending...' : 'Send reset link'}
                </button>
              </div>
            </form>
            {error && <Message kind="error">{error}</Message>}
          </>
        )}
      </div>
      <p className="auth-links">
        <Link to="/login">Log in</Link>
      </p>
    </div>
  )
}
