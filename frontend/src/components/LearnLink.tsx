import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'

// A link from inside a learn page to another page of the site — usually another
// model's flow, where a concept was covered the first time.
//
// It exists so content never writes a bare <a href="/...">. That would leave the
// SPA and reload the whole app: the router unmounts, RequireAuth re-runs, and the
// reader watches the page rebuild itself to arrive somewhere the router could
// have shown instantly. A react-router <Link> is a plain <a> in the DOM, so it
// inherits the underline from base.css and the colour from `.prose a` with no
// styling of its own — unlike SourceLink, which is sized as a control and has to
// restate what it needs.
//
// `to` is an app path, e.g. /training/step0/learn/overview. For an outbound URL
// use SourceLink instead.

export default function LearnLink({ to, children }: { to: string; children: ReactNode }) {
  return <Link to={to}>{children}</Link>
}
