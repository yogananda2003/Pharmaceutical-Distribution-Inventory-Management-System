import { apiClient, type SuccessEnvelope } from './client'

export interface Customer {
  id: string
  customer_code: string
  business_name: string
  credit_limit: string
  status: string
  email: string | null
  phone: string | null
}

export async function listCustomers(): Promise<Customer[]> {
  const res = await apiClient.get<SuccessEnvelope<Customer[]>>('/customers', {
    params: { limit: 200 },
  })
  return res.data.data
}
