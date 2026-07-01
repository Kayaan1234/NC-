import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, ApiError } from '../api/client'
import { useAuth } from '../auth/AuthContext'
import { useCountdown, formatCountdown } from '../auth/useCountdown'
import { passwordError } from '../auth/passwordPolicy'
import { EMAIL_CHANGE_COOLDOWN_HOURS, VERIFICATION_TTL_HOURS } from '../authConfig'

export default function Account() {
  const { user } = useAuth()
  if (!user) return null

  return (
    <div className="dash account">
      <p className="eyebrow mono">account settings</p>
      <h1>Your account</h1>

      <div className="card account-identity">
        <div className="identity-row">
          <span className="dash-label mono">username</span>
          <span className="dash-value">{user.username}</span>
        </div>
        <div className="identity-row">
          <span className="dash-label mono">email</span>
          <span className="dash-value">{user.email}</span>
        </div>
        <div className="identity-row">
          <span className="dash-label mono">status</span>
          <span className={user.verified ? 'pill pill-ok' : 'pill pill-warn'}>
            {user.verified ? 'verified' : 'unverified'}
          </span>
        </div>
      </div>

      {!user.verified && (
        <div className="alert alert-warn account-gate-note">
          This email isn't verified yet.{' '}
          <Link to="/verify-required">Resend the verification link →</Link>
        </div>
      )}

      <ChangeEmailCard />
      <ResetPasswordCard />
      <DeleteAccountCard />
    </div>
  )
}

function ChangeEmailCard() {
  const { refreshUser } = useAuth()
  const navigate = useNavigate()
  const [newEmail, setNewEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const { remaining, start } = useCountdown()

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy(true)
    try {
      await api.updateEmail({ new_email: newEmail, current_password: password })
      // The change flips verified -> false and updates the address server-side;
      // pull that into state, then route to the gate to verify the new address.
      await refreshUser()
      navigate('/verify-required')
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message)
        if (err.status === 429 && err.retryAfter) start(err.retryAfter)
      } else {
        setError('Something went wrong')
      }
    } finally {
      setBusy(false)
    }
  }

  const locked = remaining > 0

  return (
    <div className="card account-form">
      <h2>Change email</h2>
      <p className="lede">
        Changing your email sends a fresh verification link to the new address and marks your
        account unverified until you confirm it. You can change your email once every{' '}
        {EMAIL_CHANGE_COOLDOWN_HOURS} hours.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <form onSubmit={onSubmit} noValidate>
        <div className="field">
          <label htmlFor="new-email">new email</label>
          <input
            id="new-email"
            type="email"
            autoComplete="email"
            value={newEmail}
            onChange={(e) => setNewEmail(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="email-current-password">current password</label>
          <input
            id="email-current-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <span className="hint">Confirms it's really you before changing the address.</span>
        </div>
        <button className="btn btn-primary full" type="submit" disabled={busy || locked}>
          {busy
            ? 'updating…'
            : locked
              ? `Try again in ${formatCountdown(remaining)}`
              : 'Update email'}
        </button>
      </form>

      <p className="hint resend-note">
        The new link expires {VERIFICATION_TTL_HOURS} hours after it's sent.
      </p>
    </div>
  )
}

function ResetPasswordCard() {
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    const localError = passwordError(newPassword)
    if (localError) {
      setError(localError)
      return
    }
    if (newPassword !== confirm) {
      setError('New passwords do not match.')
      return
    }
    setError(null)
    setBusy(true)
    try {
      await api.resetPassword({ current_password: currentPassword, new_password: newPassword })
      // Server revoked every refresh token, including this one. Hand off to the
      // public confirmation page, which drops the now-dead local session on
      // mount and then counts down to /login. We must NOT clear the session
      // here: setting user=null while the protected /account route is still
      // mounted makes its guard redirect to /login before the confirmation
      // page can render.
      navigate('/password-reset', { state: { fromReset: true } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
      setBusy(false)
    }
  }

  return (
    <div className="card account-form">
      <h2>Reset password</h2>
      <p className="lede">
        Choose a new password. For your security, this signs you out of every device and you'll
        log back in with the new password.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      <form onSubmit={onSubmit} noValidate>
        <div className="field">
          <label htmlFor="reset-current-password">current password</label>
          <input
            id="reset-current-password"
            type="password"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="reset-new-password">new password</label>
          <input
            id="reset-new-password"
            type="password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            required
          />
          <span className="hint">8–30 chars · 1 uppercase · 1 digit</span>
        </div>
        <div className="field">
          <label htmlFor="reset-confirm-password">confirm new password</label>
          <input
            id="reset-confirm-password"
            type="password"
            autoComplete="new-password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
          />
        </div>
        <button className="btn btn-primary full" type="submit" disabled={busy}>
          {busy ? 'updating…' : 'Update password'}
        </button>
      </form>
    </div>
  )
}

function DeleteAccountCard() {
  const navigate = useNavigate()
  const [password, setPassword] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  // First click only arms the confirmation step — it doesn't delete anything.
  function onArm(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    if (!password) {
      setError('Enter your password to continue.')
      return
    }
    setConfirming(true)
  }

  async function onConfirmDelete() {
    setError(null)
    setBusy(true)
    try {
      await api.deleteAccount({ current_password: password })
      // Hand off to the public goodbye page, which drops the now-dead local
      // session on mount. We must NOT clear it here: setting user=null while
      // the protected /account route is still mounted makes its guard redirect
      // to /login before the goodbye page can render.
      navigate('/account-deleted', { state: { fromDelete: true } })
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Something went wrong')
      setConfirming(false)
      setBusy(false)
    }
  }

  return (
    <div className="card account-form account-danger">
      <h2>Delete account</h2>
      <p className="lede">
        Permanently delete your account and all associated data. This cannot be undone.
      </p>

      {error && <div className="alert alert-error">{error}</div>}

      {!confirming ? (
        <form onSubmit={onArm} noValidate>
          <div className="field">
            <label htmlFor="delete-password">current password</label>
            <input
              id="delete-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <span className="hint">Confirms it's really you before deleting the account.</span>
          </div>
          <button className="btn btn-danger full" type="submit">
            Delete account
          </button>
        </form>
      ) : (
        <div className="delete-confirm">
          <p className="delete-confirm-q">
            Are you sure you want to permanently delete your account? There's no going back.
          </p>
          <div className="stack-actions">
            <button className="btn btn-danger full" onClick={onConfirmDelete} disabled={busy}>
              {busy ? 'deleting…' : 'Yes, delete my account'}
            </button>
            <button
              className="btn btn-ghost full"
              onClick={() => setConfirming(false)}
              disabled={busy}
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
