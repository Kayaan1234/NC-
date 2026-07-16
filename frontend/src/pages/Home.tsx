import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

export default function Home() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  if (!user) return null

  async function resendVerification() {
    setMessage('')
    setBusy(true)
    try {
      const res = await api<{ message: string }>('/auth/resend-verification', { auth: true })
      setMessage(res.message)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : 'Could not resend')
    } finally {
      setBusy(false)
    }
  }

  async function onLogout() {
    await logout()
    navigate('/login')
  }

  return (
    <div>
      <h1>NC++</h1>
      <p>Logged in as {user.username}</p>
      <ul>
        <li>Email: {user.email}</li>
        <li>Verified: {user.verified ? 'yes' : 'no'}</li>
      </ul>
      {/* Login succeeds for unverified accounts — the server gates content, not
          the session — so the resend path has to live behind a live session. */}
      {!user.verified && (
        <button type="button" onClick={resendVerification} disabled={busy}>
          {busy ? 'Sending...' : 'Resend verification email'}
        </button>
      )}
      <p>
        <Link to="/training">Training</Link> | <Link to="/account">Account</Link>
      </p>
      <p>
        <button type="button" onClick={onLogout}>
          Log out
        </button>
      </p>
      {message && <p>{message}</p>}
    </div>
  )
}
