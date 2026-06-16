import { apiClient, type SuccessEnvelope } from './client'

export interface Medicine {
  id: string
  code: string
  name: string
  generic_name: string
  manufacturer: string
  dosage_form: string
  strength: string
  unit_type: string
  reorder_level?: number
  max_stock_level?: number
  is_active?: boolean
}

export interface MedicineCreate {
  code: string
  name: string
  generic_name: string
  manufacturer: string
  dosage_form: string
  strength: string
  unit_type: string
  reorder_level?: number
  max_stock_level?: number
}

export async function searchMedicines(q: string): Promise<Medicine[]> {
  const res = await apiClient.get<SuccessEnvelope<Medicine[]>>('/medicines/search', { params: { q } })
  return res.data.data
}

export async function listMedicines(): Promise<Medicine[]> {
  const res = await apiClient.get<SuccessEnvelope<Medicine[]>>('/medicines', { params: { limit: 200 } })
  return res.data.data
}

export async function getMedicine(id: string): Promise<Medicine> {
  const res = await apiClient.get<SuccessEnvelope<Medicine>>(`/medicines/${id}`)
  return res.data.data
}

export async function createMedicine(data: MedicineCreate): Promise<Medicine> {
  const res = await apiClient.post<SuccessEnvelope<Medicine>>('/medicines', data)
  return res.data.data
}

export async function updateMedicine(id: string, data: Partial<MedicineCreate>): Promise<Medicine> {
  const res = await apiClient.put<SuccessEnvelope<Medicine>>(`/medicines/${id}`, data)
  return res.data.data
}

export async function deleteMedicine(id: string): Promise<void> {
  await apiClient.delete(`/medicines/${id}`)
}
