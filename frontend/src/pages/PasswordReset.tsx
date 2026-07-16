import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'

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
    ;(async () => {
      if (!token) {
        setTokenError('Missing reset token')
        setChecking(false)
        return
      }
      try {
        await api<{ message: string }>('/auth/reset-password/validate', { body: { token } })
      } catch (err) {
        setTokenError(err instanceof Error ? err.message : 'Invalid or expired password reset link')
      } finally {
        setChecking(false)
      }
    })()
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
      setError(err instanceof Error ? err.message : 'Reset failed')
    } finally {
      setBusy(false)
    }
  }

  if (checking) return <p>Checking link...</p>

  return (
    <div>
      <h1>Reset password</h1>
      {tokenError && <p>{tokenError}</p>}
      {!tokenError && message && <p>{message}</p>}
      {!tokenError && !message && (
        <form onSubmit={onSubmit}>
          <div>
            <label htmlFor="new-password">New password</label>
            <br />
            <input
              id="new-password"
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              minLength={8}
              maxLength={30}
              required
            />
            <br />
            <small>8-30 characters, at least one uppercase letter and one digit.</small>
          </div>
          <button type="submit" disabled={busy}>
            {busy ? 'Resetting...' : 'Reset password'}
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
