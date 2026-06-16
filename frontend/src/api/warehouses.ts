import { apiClient, type SuccessEnvelope } from './client'

export interface Warehouse {
  id: string
  warehouse_code: string
  warehouse_name: string
  address: string | null
  capacity: number | null
  is_active: boolean
}

export interface WarehouseCreate {
  warehouse_code: string
  warehouse_name: string
  address?: string
  capacity?: number
}

export async function listWarehouses(): Promise<Warehouse[]> {
  const res = await apiClient.get<SuccessEnvelope<Warehouse[]>>('/warehouses', { params: { limit: 200 } })
  return res.data.data
}

export async function createWarehouse(data: WarehouseCreate): Promise<Warehouse> {
  const res = await apiClient.post<SuccessEnvelope<Warehouse>>('/warehouses', data)
  return res.data.data
}

export async function updateWarehouse(id: string, data: Partial<WarehouseCreate>): Promise<Warehouse> {
  const res = await apiClient.put<SuccessEnvelope<Warehouse>>(`/warehouses/${id}`, data)
  return res.data.data
}
