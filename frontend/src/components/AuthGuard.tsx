import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'

const STAFF_ROLES = ['admin', 'sales_representative', 'inventory_manager', 'warehouse_staff']

interface AuthGuardProps {
  children: ReactNode
  /** One role or list of roles allowed. Omit to allow any authenticated user. */
  roles?: string | string[]
}

export function AuthGuard({ children, roles }: AuthGuardProps) {
  const { isAuthenticated, role: userRole } = useAuth()

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (roles) {
    const allowed = Array.isArray(roles) ? roles : [roles]
    if (!userRole || !allowed.includes(userRole)) {
      if (userRole === 'customer') return <Navigate to="/customer" replace />
      if (STAFF_ROLES.includes(userRole ?? '')) return <Navigate to="/sales" replace />
      return <Navigate to="/login" replace />
    }
  }

  return <>{children}</>
}
