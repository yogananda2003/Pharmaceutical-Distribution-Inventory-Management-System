import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

interface AuthGuardProps {
  children: ReactNode
  /** If provided, user must have this role; otherwise any authenticated user passes. */
  role?: string
}

export function AuthGuard({ children, role }: AuthGuardProps) {
  const { isAuthenticated, role: userRole } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (role && userRole !== role) {
    // Redirect to the appropriate portal rather than a 403 page
    if (userRole === 'customer') return <Navigate to="/customer" replace />
    if (userRole === 'sales_representative') return <Navigate to="/sales" replace />
    return <Navigate to="/login" replace />
  }

  return <>{children}</>
}
