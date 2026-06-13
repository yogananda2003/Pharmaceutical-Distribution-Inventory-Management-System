import { apiClient, type SuccessEnvelope } from './client'

export interface LoginData {
  access_token: string
  refresh_token: string
  user_id: string
  role: string
}

export async function loginApi(email: string, password: string): Promise<LoginData> {
  const res = await apiClient.post<SuccessEnvelope<LoginData>>('/auth/login', {
    email,
    password,
  })
  return res.data.data
}

export async function logoutApi(refreshToken: string): Promise<void> {
  await apiClient.post('/auth/logout', { refresh_token: refreshToken })
}
