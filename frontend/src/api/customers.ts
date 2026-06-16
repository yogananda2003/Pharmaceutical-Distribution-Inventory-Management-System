import { apiClient, type SuccessEnvelope } from './client'

export interface Customer {
  id: string
  customer_code: string
  business_name: string
  contact_person: string | null
  email: string | null
  phone: string | null
  gst_number: string | null
  drug_license_number: string | null
  address: string | null
  credit_limit: string
  status: string
}

export interface CustomerCreate {
  customer_code: string
  business_name: string
  contact_person?: string
  email?: string
  phone?: string
  gst_number?: string
  drug_license_number?: string
  address?: string
  credit_limit?: string
  status?: string
}

export async function listCustomers(params?: { active_only?: boolean }): Promise<Customer[]> {
  const res = await apiClient.get<SuccessEnvelope<Customer[]>>('/customers', { params })
  return res.data.data
}

export async function getCustomer(id: string): Promise<Customer> {
  const res = await apiClient.get<SuccessEnvelope<Customer>>(`/customers/${id}`)
  return res.data.data
}

export async function createCustomer(data: CustomerCreate): Promise<Customer> {
  const res = await apiClient.post<SuccessEnvelope<Customer>>('/customers', data)
  return res.data.data
}

export async function updateCustomer(id: string, data: Partial<CustomerCreate>): Promise<Customer> {
  const res = await apiClient.put<SuccessEnvelope<Customer>>(`/customers/${id}`, data)
  return res.data.data
}

export async function deleteCustomer(id: string): Promise<void> {
  await apiClient.delete(`/customers/${id}`)
}
