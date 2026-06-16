import { apiClient, type SuccessEnvelope } from './client'

export interface InventoryBatch {
  id: string
  batch_number: string
  medicine_id: string
  medicine_name?: string
  warehouse_id: string
  warehouse_name?: string
  expiry_date: string
  status: string
  quantity_available: number
  quantity_reserved: number
  quantity_damaged: number
  unit_cost: string
}

export async function listBatches(params?: { medicine_id?: string; active_only?: boolean }): Promise<InventoryBatch[]> {
  const res = await apiClient.get<SuccessEnvelope<InventoryBatch[]>>('/inventory/batches', { params })
  return res.data.data
}

// Backend StockInRequest: { quantity: int, reference_number?: str }
export async function stockIn(batchId: string, quantity: number, reference?: string): Promise<InventoryBatch> {
  const res = await apiClient.post<SuccessEnvelope<InventoryBatch>>(`/inventory/batches/${batchId}/stock-in`, {
    quantity,
    reference_number: reference,
  })
  return res.data.data
}

// Backend AdjustRequest: { quantity_delta: int, reference_number?: str }
export async function adjustStock(batchId: string, quantityDelta: number, reference?: string): Promise<InventoryBatch> {
  const res = await apiClient.post<SuccessEnvelope<InventoryBatch>>(`/inventory/batches/${batchId}/adjust`, {
    quantity_delta: quantityDelta,   // NOT "quantity", NOT "reason"
    reference_number: reference,
  })
  return res.data.data
}

// Backend DamageRequest: { quantity: int, reference_number?: str }
export async function damageStock(batchId: string, quantity: number, reference?: string): Promise<InventoryBatch> {
  const res = await apiClient.post<SuccessEnvelope<InventoryBatch>>(`/inventory/batches/${batchId}/damage`, {
    quantity,
    reference_number: reference,   // NOT "reason"
  })
  return res.data.data
}
