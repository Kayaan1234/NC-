import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'
import Message from '../components/Message'
import { message as toMessage } from '../train'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const { user, reload } = useAuth()
  // One string used to carry all three outcomes before — "Verifying...", the
  // success message and every failure looked identical. The kind travels with the
  // text now so the message can show which of the three this is.
  const [state, setState] = useState<{ kind: 'info' | 'ok' | 'error'; text: string }>({
    kind: 'info',
    text: 'Verifying...',
  })
  const ok = state.kind === 'ok'
  // The token is single-use, so React 18+ StrictMode's double-mount in dev would
  // burn it on the first call and show "invalid link" from the second.
  const sent = useRef(false)

  // Deliberately NOT cancelled on cleanup, unlike the other pages' fetches. The
  // two guards would fight: StrictMode runs effect → cleanup → effect, so a
  // cancelled flag set by that cleanup would discard the first call's result
  // while `sent` blocks the second call from ever replacing it, leaving the page
  // stuck on "Verifying..." in dev. The single-use token means the request must
  // happen exactly once and its answer must land, so the ref wins here; the cost
  // is one no-op setState if you navigate away mid-request.
  useEffect(() => {
    if (sent.current) return
    sent.current = true
    ;(async () => {
      if (!token) {
        setState({ kind: 'error', text: 'Missing verification token' })
        return
      }
      try {
        const res = await api<{ message: string }>('/auth/verify', { body: { token } })
        setState({ kind: 'ok', text: res.message })
      } catch (err) {
        setState({ kind: 'error', text: toMessage(err, 'Verification failed') })
      }
    })()
  }, [token])

  // Verifying in an already-logged-in tab leaves the cached user saying
  // verified:false. This can't live in the effect above: that one runs before the
  // mount-time session bootstrap has populated `user`, and its single-use guard
  // stops it re-running once `user` lands. Refetching when `user` becomes known
  // settles once — the reload flips verified to true, which closes the condition.
  useEffect(() => {
    if (ok && user && !user.verified) reload().catch(() => {})
  }, [ok, user, reload])

  return (
    <div className="container-form">
      <div className="card">
        <h1 className="card__title">Verify email</h1>
        <Message kind={state.kind}>{state.text}</Message>
      </div>
      <p className="auth-links">
        {ok ? <Link to="/">Continue</Link> : <Link to="/login">Log in</Link>}
      </p>
    </div>
  )
}
