import { apiClient, type SuccessEnvelope } from './client'

export interface Supplier {
  id: string
  supplier_code: string
  supplier_name: string   // backend field name — NOT "name"
  email: string | null
  phone: string | null
  address: string | null
  status: string
}

export interface SupplierCreate {
  supplier_code: string
  supplier_name: string   // must match backend field name
  email?: string
  phone?: string
  address?: string
}

export async function listSuppliers(): Promise<Supplier[]> {
  const res = await apiClient.get<SuccessEnvelope<Supplier[]>>('/suppliers', { params: { limit: 200 } })
  return res.data.data
}

export async function createSupplier(data: SupplierCreate): Promise<Supplier> {
  const res = await apiClient.post<SuccessEnvelope<Supplier>>('/suppliers', data)
  return res.data.data
}

export async function updateSupplier(id: string, data: Partial<SupplierCreate>): Promise<Supplier> {
  const res = await apiClient.put<SuccessEnvelope<Supplier>>(`/suppliers/${id}`, data)
  return res.data.data
}

export async function deleteSupplier(id: string): Promise<void> {
  await apiClient.delete(`/suppliers/${id}`)
}
