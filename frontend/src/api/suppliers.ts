import { apiClient, type SuccessEnvelope } from './client'

export interface Supplier {
  id: string
  supplier_code: string
  supplier_name: string
  contact_person: string | null
  email: string | null
  phone: string | null
  gst_number: string | null
  drug_license_number: string | null
  address: string | null
  status: string
}

export interface SupplierCreate {
  supplier_code: string
  supplier_name: string
  contact_person?: string
  email?: string
  phone?: string
  gst_number?: string
  drug_license_number?: string
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
