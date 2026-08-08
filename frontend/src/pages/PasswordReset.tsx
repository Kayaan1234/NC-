import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import Message from '../components/Message'
import { message as toMessage } from '../train'

export default function PasswordReset() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const [checking, setChecking] = useState(true)
  const [tokenError, setTokenError] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  // Check the link before showing the form. /validate is read-only — it applies
  // the same criteria as the reset itself without consuming the single-use token.
  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!token) {
        setTokenError('Missing reset token')
        setChecking(false)
        return
      }
      try {
        await api<{ message: string }>('/auth/reset-password/validate', { body: { token } })
      } catch (err) {
        if (!cancelled) setTokenError(toMessage(err, 'Invalid or expired password reset link'))
      } finally {
        if (!cancelled) setChecking(false)
      }
    })()
    return () => {
      cancelled = true
    }
  }, [token])

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const res = await api<{ message: string }>('/auth/reset-password', {
        body: { token, new_password: newPassword },
      })
      setMessage(res.message)
    } catch (err) {
      setError(toMessage(err, 'Reset failed'))
    } finally {
      setBusy(false)
    }
  }

  if (checking) return <p className="page-status">Checking link...</p>

  return (
    <div className="container-form">
      <div className="card">
        <h1 className="card__title">Reset password</h1>
        {tokenError && <Message kind="error">{tokenError}</Message>}
        {!tokenError && message && <Message kind="ok">{message}</Message>}
        {!tokenError && !message && (
          <>
            <form onSubmit={onSubmit}>
              <div className="field">
                <label htmlFor="new-password">New password</label>
                <input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  minLength={8}
                  maxLength={30}
                  required
                />
                <small className="field__hint">
                  8-30 characters, at least one uppercase letter and one digit.
                </small>
              </div>
              <div className="form-actions">
                <button type="submit" className="btn-primary" disabled={busy}>
                  {busy ? 'Resetting...' : 'Reset password'}
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
