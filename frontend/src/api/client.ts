import axios from 'axios'
import { clearAuth, getRefreshToken, getToken, setAuth } from '../lib/auth'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
})

// ── Request interceptor: attach the access token ──────────────────────────────
apiClient.interceptors.request.use((config) => {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// ── Response interceptor: auto-refresh on 401 ─────────────────────────────────
// Prevents multiple simultaneous refreshes by queuing retries while one is in flight.
let isRefreshing = false
let waitQueue: Array<(token: string) => void> = []

function drainQueue(newToken: string) {
  waitQueue.forEach(cb => cb(newToken))
  waitQueue = []
}

apiClient.interceptors.response.use(
  res => res,
  async (error) => {
    const original = error.config as typeof error.config & { _retry?: boolean }

    // Only attempt a refresh for 401s on the first failure (not the refresh call itself)
    if (error.response?.status === 401 && !original._retry && !original.url?.includes('/auth/refresh')) {
      if (isRefreshing) {
        // Another request already triggered a refresh — queue this one
        return new Promise((resolve) => {
          waitQueue.push((token: string) => {
            original.headers.Authorization = `Bearer ${token}`
            resolve(apiClient(original))
          })
        })
      }

      original._retry = true
      isRefreshing = true

      const refreshToken = getRefreshToken()
      if (!refreshToken) {
        isRefreshing = false
        clearAuth()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      try {
        // Call refresh — use a raw axios call to avoid re-triggering this interceptor
        const res = await axios.post<SuccessEnvelope<{
          access_token: string; refresh_token: string; role: string; user_id: string
        }>>(
          `${apiClient.defaults.baseURL}/auth/refresh`,
          { refresh_token: refreshToken },
        )
        const { access_token, refresh_token, role, user_id } = res.data.data
        setAuth(access_token, refresh_token, role, String(user_id))
        isRefreshing = false
        drainQueue(access_token)
        original.headers.Authorization = `Bearer ${access_token}`
        return apiClient(original)
      } catch {
        isRefreshing = false
        clearAuth()
        window.location.href = '/login'
        return Promise.reject(error)
      }
    }

    return Promise.reject(error)
  },
)

export interface SuccessEnvelope<T> {
  success: true
  data: T
}

export interface ErrorEnvelope {
  success: false
  message: string
}

export type ApiEnvelope<T> = SuccessEnvelope<T> | ErrorEnvelope

// Extracts a human-readable message from FastAPI error responses
export function extractApiError(e: unknown, fallback = 'Request failed'): string {
  console.error('[API Error]', e)

  const err = e as {
    message?: string
    response?: { status?: number; data?: { detail?: unknown; message?: string } }
  }

  if (!err.response) {
    return `Network error: ${err.message ?? 'cannot reach server'}. Is the backend running on port 8000?`
  }

  const { status, data } = err.response
  if (!data) return `HTTP ${status} — ${fallback}`

  const detail = data.detail
  if (Array.isArray(detail)) {
    return detail.map((d: { loc?: string[]; msg?: string }) => {
      const field = d.loc?.slice(-1)[0] ?? ''
      return field ? `${field}: ${d.msg}` : d.msg ?? JSON.stringify(d)
    }).join('; ')
  }
  if (typeof detail === 'string') return `${detail} (HTTP ${status})`
  if (data.message) return data.message
  return `HTTP ${status} — ${fallback}`
}
