import { Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Register from './pages/Register'
import Dashboard from './pages/Dashboard'
import VerifyEmail from './pages/VerifyEmail'
import VerifyRequired from './pages/VerifyRequired'
import Account from './pages/Account'
import ForgotPassword from './pages/ForgotPassword'
import PasswordReset from './pages/PasswordReset'
import AccountDeleted from './pages/AccountDeleted'

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        {/* Public: reached from the login page; posts the email and shows a
            generic "if it's registered…" confirmation (no enumeration). */}
        <Route path="/forgot-password" element={<ForgotPassword />} />
        {/* Public: the link lands here from the verification email, and the
            clicker may have no session (different device/browser). */}
        <Route path="/verify-email" element={<VerifyEmail />} />
        {/* Logged-in gate for unverified users — NOT itself verified-gated. */}
        <Route
          path="/verify-required"
          element={
            <ProtectedRoute>
              <VerifyRequired />
            </ProtectedRoute>
          }
        />
        <Route
          path="/account"
          element={
            <ProtectedRoute>
              <Account />
            </ProtectedRoute>
          }
        />
        {/* Public result pages — the session is already gone by the time these
            render (password reset revokes it; delete removes the user). They
            self-guard against direct visits via router state. */}
        <Route path="/password-reset" element={<PasswordReset />} />
        <Route path="/account-deleted" element={<AccountDeleted />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute requireVerified>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}
