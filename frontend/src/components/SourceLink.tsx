import type { ReactNode } from 'react'

// A "read the real thing" link out to the source on GitHub, sized as a control
// rather than as body text — it is the one action on an otherwise passive page.
//
// It is an <a>, not a <button>: it navigates. That means it inherits none of the
// button styling in forms.css (which hangs off the bare `button` element
// selector), so .source-link restates the properties it needs — see prose.css.
//
// `rel="noreferrer noopener"` on a target=_blank link is not optional: without
// `noopener` the opened page gets a handle on this window via `window.opener`.
// No third-party script is loaded either way, which the privacy policy promises;
// this is an ordinary outbound link the reader chooses to follow.

export default function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a className="source-link" href={href} target="_blank" rel="noreferrer noopener">
      {children}
      <span aria-hidden="true"> ↗</span>
    </a>
  )
}
