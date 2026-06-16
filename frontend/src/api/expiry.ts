import { apiClient, type SuccessEnvelope } from './client'

export interface BatchExpiryInfo {
  batch_id: string
  batch_number: string
  medicine_id: string
  medicine_code: string
  medicine_name: string
  warehouse_id: string
  warehouse_name: string
  expiry_date: string
  days_to_expiry: number
  quantity_available: number
  quantity_reserved: number
  alert_level: string
}

export interface ExpiryDashboard {
  as_of: string
  expired_count: number
  expiring_within_30d: number
  expiring_within_60d: number
  expiring_within_90d: number
}

export async function getExpiryDashboard(): Promise<ExpiryDashboard> {
  const res = await apiClient.get<SuccessEnvelope<ExpiryDashboard>>('/expiry/dashboard')
  return res.data.data
}

export async function getExpiredBatches(): Promise<BatchExpiryInfo[]> {
  const res = await apiClient.get<SuccessEnvelope<BatchExpiryInfo[]>>('/expiry/expired')
  return res.data.data
}

export async function getNearExpiryBatches(days = 30): Promise<BatchExpiryInfo[]> {
  const res = await apiClient.get<SuccessEnvelope<BatchExpiryInfo[]>>('/expiry/near-expiry', {
    params: { days },
  })
  return res.data.data
}
