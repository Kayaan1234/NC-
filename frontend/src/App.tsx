import { Navigate, Route, Routes } from 'react-router-dom'
import { useAuth } from './auth'
import Account from './pages/Account'
import Home from './pages/Home'
import Login from './pages/Login'
import Register from './pages/Register'
import Training from './pages/Training'
import TrainingModel from './pages/TrainingModel'
import ForgotPassword from './pages/ForgotPassword'
import PasswordReset from './pages/PasswordReset'
import VerifyEmail from './pages/VerifyEmail'
import Privacy from './pages/Privacy'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  // Wait for the mount-time /auth/refresh to settle, or a reload would bounce a
  // logged-in user to /login before their session is restored.
  if (loading) return <p>Loading...</p>
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) return <p>Loading...</p>
  if (user) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <Routes>
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
    </Routes>
  )
}
