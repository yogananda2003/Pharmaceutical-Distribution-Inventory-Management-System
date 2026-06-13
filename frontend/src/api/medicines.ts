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
}

export async function searchMedicines(q: string): Promise<Medicine[]> {
  const res = await apiClient.get<SuccessEnvelope<Medicine[]>>('/medicines/search', {
    params: { q },
  })
  return res.data.data
}

export async function listMedicines(): Promise<Medicine[]> {
  const res = await apiClient.get<SuccessEnvelope<Medicine[]>>('/medicines', {
    params: { limit: 200 },
  })
  return res.data.data
}
