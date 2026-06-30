import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

interface Props {
  children: ReactNode
  // When set, a logged-in-but-unverified user is bounced to the verify gate
  // instead of seeing the page. Used to lock the dashboard behind verification.
  requireVerified?: boolean
}

export default function ProtectedRoute({ children, requireVerified = false }: Props) {
  const { user, loading } = useAuth()

  if (loading) {
    return <div className="page-loading mono">resolving session…</div>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  if (requireVerified && !user.verified) {
    return <Navigate to="/verify-required" replace />
  }
  return <>{children}</>
}
