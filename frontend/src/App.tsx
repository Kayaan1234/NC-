import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Layout from './components/Layout'
import Account from './pages/Account'
import Home from './pages/Home'
import Login from './pages/Login'
import Register from './pages/Register'
import Training from './pages/Training'
import TrainingModel from './pages/TrainingModel'
import Learn from './pages/Learn'
import ForgotPassword from './pages/ForgotPassword'
import PasswordReset from './pages/PasswordReset'
import VerifyEmail from './pages/VerifyEmail'
import Privacy from './pages/Privacy'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  // Wait for the mount-time /auth/refresh to settle, or a reload would bounce a
  // logged-in user to /login before their session is restored.
  if (loading) return <p className="page-status">Restoring session...</p>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <p className="page-status">Restoring session...</p>
  if (user) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
      {/* Layout route: every page below renders inside the shell (top bar, footer),
          including the public ones. Pages set their own width by picking a
          container class — see components/Layout.tsx. */}
      <Route element={<Layout />}>
        <Route
          path="/"
          element={
            <RequireAuth>
              <Home />
            </RequireAuth>
          }
        />
        <Route
          path="/account"
          element={
            <RequireAuth>
              <Account />
            </RequireAuth>
          }
        />
        {/* SPA path is /training, deliberately NOT /train: the API prefix is /train,
            and a full-page load of a SPA route that shadows it gets proxied to the
            backend (dev) / nginx (prod) instead of served as the app. Logged-in gate
            only; the page handles the verified-email gate itself, like Home, since
            the server 403s unverified /train calls anyway. */}
        <Route
          path="/training"
          element={
            <RequireAuth>
              <Training />
            </RequireAuth>
          }
        />
        {/* Per-model config page, reached from the /training menu. Same /training
            prefix (deliberately not /train — see the comment above) so it isn't
            proxied to the backend on a full-page load. */}
        <Route
          path="/training/:modelId"
          element={
            <RequireAuth>
              <TrainingModel />
            </RequireAuth>
          }
        />
        {/* "Read about the model" flow that precedes training for models with
            authored content. Logged-in gate only (deliberately NOT verified-email):
            reading is static, makes no /train call, and motivates verifying. Same
            /training prefix as above so it isn't proxied to the backend. The bare
            path renders the first section; :slug renders a specific one. */}
        <Route
          path="/training/:modelId/learn"
          element={
            <RequireAuth>
              <Learn />
            </RequireAuth>
          }
        />
        <Route
          path="/training/:modelId/learn/:slug"
          element={
            <RequireAuth>
              <Learn />
            </RequireAuth>
          }
        />
        <Route
          path="/login"
          element={
            <PublicOnly>
              <Login />
            </PublicOnly>
          }
        />
        <Route
          path="/register"
          element={
            <PublicOnly>
              <Register />
            </PublicOnly>
          }
        />
        <Route
          path="/forgot-password"
          element={
            <PublicOnly>
              <ForgotPassword />
            </PublicOnly>
          }
        />
        {/* Reached from an email link, which may land in a browser that is already
            logged in — so these two are not PublicOnly. */}
        <Route path="/password-reset" element={<PasswordReset />} />
        <Route path="/verify-email" element={<VerifyEmail />} />
        {/* Public legal page: readable logged in OR out, so no gate wrapper. */}
        <Route path="/privacy" element={<Privacy />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
