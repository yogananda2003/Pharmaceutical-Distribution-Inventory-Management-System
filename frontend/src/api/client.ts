import axios from 'axios'

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1',
})

export interface SuccessEnvelope<T> {
  success: true
  data: T
}

export interface ErrorEnvelope {
  success: false
  message: string
}

export type ApiEnvelope<T> = SuccessEnvelope<T> | ErrorEnvelope
