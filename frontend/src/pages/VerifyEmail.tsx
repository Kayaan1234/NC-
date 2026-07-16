import { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api'
import { useAuth } from '../auth'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token') ?? ''
  const { user, reload } = useAuth()
  const [status, setStatus] = useState('Verifying...')
  const [ok, setOk] = useState(false)
  // The token is single-use, so React 18+ StrictMode's double-mount in dev would
  // burn it on the first call and show "invalid link" from the second.
  const sent = useRef(false)

  useEffect(() => {
    if (sent.current) return
    sent.current = true
    ;(async () => {
      if (!token) {
        setStatus('Missing verification token')
        return
      }
      try {
        const res = await api<{ message: string }>('/auth/verify', { body: { token } })
        setStatus(res.message)
        setOk(true)
      } catch (err) {
        setStatus(err instanceof Error ? err.message : 'Verification failed')
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
    <div>
      <h1>Verify email</h1>
      <p>{status}</p>
      <p>{ok ? <Link to="/">Continue</Link> : <Link to="/login">Log in</Link>}</p>
    </div>
  )
}
