const TOKEN_KEY = 'pharma_token'
const REFRESH_KEY = 'pharma_refresh'
const ROLE_KEY = 'pharma_role'
const USER_ID_KEY = 'pharma_user_id'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getRole(): string | null {
  return localStorage.getItem(ROLE_KEY)
}

export function getUserId(): string | null {
  return localStorage.getItem(USER_ID_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function setAuth(token: string, refreshToken: string, role: string, userId: string): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(REFRESH_KEY, refreshToken)
  localStorage.setItem(ROLE_KEY, role)
  localStorage.setItem(USER_ID_KEY, userId)
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
  localStorage.removeItem(ROLE_KEY)
  localStorage.removeItem(USER_ID_KEY)
}
