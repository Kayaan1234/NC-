import type { ReactNode } from 'react'

// Before this component every page rendered errors and successes identically, as
// a bare <p>{text}</p> — a failed login and a sent verification email looked the
// same. The severity now lives in a left rule, which is enough to distinguish them
// at a glance without turning a form validation notice into a banner.
//
//   error  something the user must act on before continuing
//   ok     something completed
//   info   a neutral standing condition (unverified email, a check in progress)

type Kind = 'error' | 'ok' | 'info'

export default function Message({
  kind,
  children,
  role,
}: {
  kind: Kind
  children: ReactNode
  role?: 'status' | 'alert'
}) {
  return (
    <div
      className={`msg msg--${kind}`}
      // Errors interrupt; everything else is announced politely when the
      // screen reader next has a gap. Callers can override for a live region
      // that should not announce at all.
      role={role ?? (kind === 'error' ? 'alert' : 'status')}
    >
      <div className="msg__body">{children}</div>
    </div>
  )
}
