import { Link, NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth'

// The app shell. Until this existed every page hand-rolled its own navigation —
// "Home" at the bottom of four pages, "← All models" at the top of two, and Log
// out reachable only from the home page — so the same links appeared in different
// places with different wording depending on where you were.
//
// Mounted as a react-router layout route in App.tsx, so every route renders inside
// it, including the public ones (/privacy, /verify-email, /password-reset).
//
// <main> deliberately sets no width of its own: each page picks a container class
// instead. That keeps this component from having to inspect the current route to
// decide how wide the content should be, and lets the learn page's rail run to the
// edge of the viewport rather than fighting a max-width it never wanted.

export default function Layout() {
  const { user, logout } = useAuth()

  async function onLogout() {
    // Local state drops regardless of the server's answer (see auth.tsx), and the
    // RequireAuth gate then redirects off any authenticated route on its own.
    await logout().catch(() => {})
  }

  return (
    <div className="shell">
      <header className="topbar">
        <Link to="/" className="topbar__brand">
          NC++
        </Link>
        {/* This used to be empty when logged out, on the grounds that /login and
            /register were the only public pages and a bar link would just point at
            the page you were already on. That stopped being true when / became the
            public landing page: a visitor reading it is on neither, and the way in
            has to be somewhere. */}
        {user ? (
          <nav className="topbar__nav">
            <NavLink to="/training">training</NavLink>
            <NavLink to="/account">account</NavLink>
            <button type="button" className="topbar__link" onClick={onLogout}>
              log out
            </button>
          </nav>
        ) : (
          <nav className="topbar__nav">
            <NavLink to="/login">log in</NavLink>
            <NavLink to="/register">register</NavLink>
          </nav>
        )}
      </header>

      <main>
        <Outlet />
      </main>

      <footer className="footer">
        <Link to="/privacy">Privacy Policy</Link>
      </footer>
    </div>
  )
}
