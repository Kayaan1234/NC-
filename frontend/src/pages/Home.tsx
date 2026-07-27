import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Message from '../components/Message'
import { message as toMessage } from '../train'

// The page you land on after logging in. Log out and the nav links moved to the
// shell, so what's left has to justify the route on its own: it states who you're
// signed in as, and points at the one thing there is to do. When the account isn't
// verified that's the only thing on the page that matters, so it leads.

export default function Home() {
  const { user } = useAuth()
  const [result, setResult] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [busy, setBusy] = useState(false)

  if (!user) return null

  async function resendVerification() {
    setResult(null)
    setBusy(true)
    try {
      const res = await api<{ message: string }>('/auth/resend-verification', { auth: true })
      setResult({ kind: 'ok', text: res.message })
    } catch (err) {
      setResult({ kind: 'error', text: toMessage(err, 'Could not resend') })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="container-app">
      <div className="page-header">
        <h1>NC++</h1>
        <p>Neural network implementations in C++, and the training runs behind them.</p>
      </div>

      {/* Login succeeds for unverified accounts — the server gates content, not
          the session — so the resend path has to live behind a live session. */}
      {!user.verified && (
        <Message kind="info">
          <p>Your email isn&rsquo;t verified yet, so training is unavailable.</p>
          <p className="msg__actions">
            <button type="button" onClick={resendVerification} disabled={busy}>
              {busy ? 'Sending...' : 'Resend verification email'}
            </button>
          </p>
        </Message>
      )}

      {result && <Message kind={result.kind}>{result.text}</Message>}

      <div className="section">
        <h2 className="section__title">Account</h2>
        <div className="card">
          <dl className="kv">
            <dt>user</dt>
            <dd>{user.username}</dd>
            <dt>email</dt>
            <dd>{user.email}</dd>
            <dt>verified</dt>
            <dd>
              <span className={user.verified ? 'status status--succeeded' : 'status status--queued'}>
                {user.verified ? 'yes' : 'no'}
              </span>
            </dd>
          </dl>
        </div>
      </div>

      <div className="section">
        <h2 className="section__title">Training</h2>
        <Link to="/training" className="model">
          <div className="model__name">Models &rarr;</div>
          <div className="model__desc">
            Read through a model&rsquo;s source, then run it and download the report.
          </div>
        </Link>
      </div>
    </div>
  )
}
