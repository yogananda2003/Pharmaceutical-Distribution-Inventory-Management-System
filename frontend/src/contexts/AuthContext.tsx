import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { loginApi, logoutApi } from '../api/auth'
import { clearAuth, getRefreshToken, getRole, getToken, getUserId, setAuth } from '../lib/auth'

interface AuthState {
  token: string | null
  role: string | null
  userId: string | null
}

interface AuthContextValue extends AuthState {
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

// eslint-disable-next-line react-refresh/only-export-components
export const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [auth, setAuthState] = useState<AuthState>({
    token: getToken(),
    role: getRole(),
    userId: getUserId(),
  })

  const login = useCallback(async (email: string, password: string) => {
    const data = await loginApi(email, password)
    setAuth(data.access_token, data.refresh_token, data.role, data.user_id)
    setAuthState({ token: data.access_token, role: data.role, userId: data.user_id })
  }, [])

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken()
    if (refreshToken) {
      try {
        await logoutApi(refreshToken)
      } catch {
        // best-effort
      }
    }
    clearAuth()
    setAuthState({ token: null, role: null, userId: null })
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      ...auth,
      isAuthenticated: !!auth.token,
      login,
      logout,
    }),
    [auth, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
