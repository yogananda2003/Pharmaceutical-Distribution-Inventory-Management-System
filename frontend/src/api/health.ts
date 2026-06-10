import { useQuery } from '@tanstack/react-query'
import { apiClient, type ApiEnvelope } from './client'

interface HealthStatus {
  status: string
}

async function fetchHealth(): Promise<ApiEnvelope<HealthStatus>> {
  const { data } = await apiClient.get<ApiEnvelope<HealthStatus>>('/health')
  return data
}

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: fetchHealth,
  })
}
