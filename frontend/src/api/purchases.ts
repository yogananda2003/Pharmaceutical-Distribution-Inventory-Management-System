import { apiClient, type SuccessEnvelope } from './client'

export interface POItem {
  id: string
  medicine_id: string
  medicine_name?: string
  quantity_ordered: number
  quantity_received: number
  unit_price: string
}

export interface PurchaseOrder {
  id: string
  po_number: string
  supplier_id: string
  supplier_name?: string
  order_date: string
  expected_delivery_date: string | null
  status: string
  notes: string | null
  items: POItem[]
}

export interface POItemCreate {
  medicine_id: string
  quantity_ordered: number
  unit_price: string
}

export interface POCreate {
  supplier_id: string
  order_date: string
  expected_delivery_date?: string
  notes?: string
  items: POItemCreate[]
}

export interface ReceiveItem {
  medicine_id: string
  quantity_received: number
  batch_number: string
  expiry_date: string
  warehouse_id: string
  unit_cost: string
}

export interface ReceivePayload {
  received_date: string
  items: ReceiveItem[]
}

export async function listPurchaseOrders(params?: { supplier_id?: string; status?: string }): Promise<PurchaseOrder[]> {
  const res = await apiClient.get<SuccessEnvelope<PurchaseOrder[]>>('/purchases', { params })
  return res.data.data
}

export async function getPurchaseOrder(id: string): Promise<PurchaseOrder> {
  const res = await apiClient.get<SuccessEnvelope<PurchaseOrder>>(`/purchases/${id}`)
  return res.data.data
}

export async function createPurchaseOrder(data: POCreate): Promise<PurchaseOrder> {
  const res = await apiClient.post<SuccessEnvelope<PurchaseOrder>>('/purchases', data)
  return res.data.data
}

export async function updatePOStatus(id: string, status: string): Promise<PurchaseOrder> {
  const res = await apiClient.patch<SuccessEnvelope<PurchaseOrder>>(`/purchases/${id}/status`, { status })
  return res.data.data
}

export async function receiveGoods(id: string, payload: ReceivePayload): Promise<PurchaseOrder> {
  const res = await apiClient.post<SuccessEnvelope<PurchaseOrder>>(`/purchases/${id}/receive`, payload)
  return res.data.data
}
