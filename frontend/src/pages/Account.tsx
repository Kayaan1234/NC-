import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

function message(err: unknown, fallback: string): string {
  return err instanceof Error ? err.message : fallback
}

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
    <form onSubmit={onSubmit}>
      <h2>Change password</h2>
      <div>
        <label htmlFor="cp-current">Current password</label>
        <br />
        <input
          id="cp-current"
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </div>
      <div>
        <label htmlFor="cp-new">New password</label>
        <br />
        <input
          id="cp-new"
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
        {busy ? 'Updating...' : 'Update password'}
      </button>
      <p>You will be logged out and need to log in again.</p>
      {error && <p>{error}</p>}
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
    <form onSubmit={onSubmit}>
      <h2>Change email</h2>
      <div>
        <label htmlFor="ce-email">New email</label>
        <br />
        <input
          id="ce-email"
          type="email"
          value={newEmail}
          onChange={(e) => setNewEmail(e.target.value)}
          required
        />
      </div>
      <div>
        <label htmlFor="ce-password">Current password</label>
        <br />
        <input
          id="ce-password"
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </div>
      <button type="submit" disabled={busy}>
        {busy ? 'Updating...' : 'Update email'}
      </button>
      <p>Changing your email marks it unverified until you use the new link. Once per day.</p>
      {result && <p>{result}</p>}
      {error && <p>{error}</p>}
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

  return (
    <form onSubmit={onSubmit}>
      <h2>Delete account</h2>
      <div>
        <label htmlFor="da-password">Current password</label>
        <br />
        <input
          id="da-password"
          type="password"
          value={currentPassword}
          onChange={(e) => setCurrentPassword(e.target.value)}
          required
        />
      </div>
      <button type="submit" disabled={busy}>
        {busy ? 'Deleting...' : 'Delete account permanently'}
      </button>
      <p>This cannot be undone.</p>
      {error && <p>{error}</p>}
    </form>
  )
}

export default function Account() {
  const { user } = useAuth()

  if (!user) return null

  return (
    <div>
      <h1>Account</h1>
      <ul>
        <li>Username: {user.username}</li>
        <li>Email: {user.email}</li>
        <li>Verified: {user.verified ? 'yes' : 'no'}</li>
      </ul>
      <ChangePassword />
      <hr />
      <ChangeEmail />
      <hr />
      <DeleteAccount />
      <p>
        <Link to="/">Home</Link>
      </p>
    </div>
  )
}
