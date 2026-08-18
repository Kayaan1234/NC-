import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Message from '../components/Message'
import { message } from '../train'

function ChangePassword() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api<{ message: string }>('/users/me/password', {
        method: 'PATCH',
        auth: true,
        body: { current_password: currentPassword, new_password: newPassword },
      })
      // The server just revoked every refresh token and cleared the cookie, so
      // this session is already dead — but our in-memory access token stays
      // cryptographically valid until it expires, and get_current_user checks
      // neither revocation nor is_active. Staying put would leave a zombie
      // logged-in state, so discarding the token here isn't a UX choice.
      await logout()
      navigate('/login')
    } catch (err) {
      setError(message(err, 'Could not update password'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={onSubmit}>
      <h2 className="card__title">Change password</h2>
      <div className="field">
        <label htmlFor="cp-current">Current password</label>
        <input
          id="cp-current"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </div>
      <div className="field">
        <label htmlFor="cp-new">New password</label>
        <input
          id="cp-new"
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
        <button type="submit" disabled={busy}>
          {busy ? 'Updating...' : 'Update password'}
        </button>
      </div>
      <p className="card__note">You will be logged out and need to log in again.</p>
      {error && <Message kind="error">{error}</Message>}
    </form>
  )
}

function ChangeEmail() {
  const { reload } = useAuth()
  const [newEmail, setNewEmail] = useState('')
  const [currentPassword, setCurrentPassword] = useState('')
  const [result, setResult] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setResult('')
    setBusy(true)
    try {
      const res = await api<{ message: string }>('/users/me/email', {
        method: 'PATCH',
        auth: true,
        body: { new_email: newEmail, current_password: currentPassword },
      })
      setResult(res.message)
      setNewEmail('')
      setCurrentPassword('')
      // Unlike the password path this keeps the session alive, but it flips
      // verified back to false and changes the address — refetch so the page
      // stops showing the old one.
      await reload()
    } catch (err) {
      setError(message(err, 'Could not update email'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="card" onSubmit={onSubmit}>
      <h2 className="card__title">Change email</h2>
      <div className="field">
        <label htmlFor="ce-email">New email</label>
        <input
          id="ce-email"
          type="email"
          autoComplete="email"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          required
        />
      </div>
      <div className="field">
        <label htmlFor="ce-password">Current password</label>
        <input
          id="ce-password"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </div>
      <div className="form-actions">
        <button type="submit" disabled={busy}>
          {busy ? 'Updating...' : 'Update email'}
        </button>
      </div>
      <p className="card__note">
        Changing your email marks it unverified until you follow the new link. Once a day, at most.
      </p>
      {result && <Message kind="ok">{result}</Message>}
      {error && <Message kind="error">{error}</Message>}
    </form>
  )
}

function DeleteAccount() {
  const { logout } = useAuth()
  const navigate = useNavigate()
  const [currentPassword, setCurrentPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      await api<void>('/users/me', {
        method: 'DELETE',
        auth: true,
        body: { current_password: currentPassword },
      })
      // Same zombie-session reasoning as the password path: the row (and its
      // tokens) are gone, but our access token would still decode until it
      // expires — get_current_user would 401 only because the user lookup now
      // misses. Drop it explicitly rather than rely on that.
      await logout()
      navigate('/login')
    } catch (err) {
      setError(message(err, 'Could not delete account'))
    } finally {
      setBusy(false)
    }
  }

  // The only irreversible action in the app, and until now it looked exactly like
  // the two ordinary forms above it. The card gets a red left edge, the warning is
  // stated before the control rather than after it, and the button is outlined in
  // --err so it reads as dangerous without shouting from across the page.
  return (
    <form className="card card--danger" onSubmit={onSubmit}>
      <h2 className="card__title">Delete account</h2>
      <Message kind="error">
        This permanently deletes your account, your training jobs and their reports. It cannot be
        undone.
      </Message>
      <div className="field">
        <label htmlFor="da-password">Current password</label>
        <input
          id="da-password"
          type="password"
          autoComplete="current-password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </div>
      <div className="form-actions">
        <button type="submit" className="btn-danger" disabled={busy}>
          {busy ? 'Deleting...' : 'Delete account permanently'}
        </button>
      </div>
      {error && <Message kind="error">{error}</Message>}
    </form>
  )
}

export default function Account() {
  const { user } = useAuth()

  if (!user) return null

  return (
    <div className="container-app">
      <div className="page-header">
        <h1>Account</h1>
      </div>

      <div className="card">
        <dl className="kv">
          <dt>user</dt>
          <dd>{user.username}</dd>
          <dt>email</dt>
          <dd>{user.email}</dd>
          <dt>verified</dt>
          <dd>
            <span
              className={user.verified ? 'status status--succeeded' : 'status status--queued'}
            >
              {user.verified ? 'yes' : 'no'}
            </span>
          </dd>
        </dl>
      </div>

      <div className="section">
        <h2 className="section__title">Settings</h2>
        <ChangePassword />
        <ChangeEmail />
      </div>

      <div className="section">
        <h2 className="section__title">Danger zone</h2>
        <DeleteAccount />
      </div>
    </div>
  )
}
