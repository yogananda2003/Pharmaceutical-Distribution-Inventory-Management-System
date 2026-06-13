import { apiClient, type SuccessEnvelope } from './client'

export interface OrderItemCreate {
  medicine_id: string
  quantity: number
  unit_price: string
  discount: string
  tax_amount: string
}

export interface CreateOrderPayload {
  customer_id: string
  order_date: string
  items: OrderItemCreate[]
}

export interface OrderItemRead {
  id: string
  medicine_id: string
  medicine_name?: string | null
  quantity: number
  unit_price: string
  discount: string
  tax_amount: string
  line_total: string
}

export interface Order {
  id: string
  order_number: string
  customer_id: string
  order_date: string
  status: string
  total_amount: string
  notes: string | null
  items: OrderItemRead[]
}

export async function createOrder(payload: CreateOrderPayload): Promise<Order> {
  const res = await apiClient.post<SuccessEnvelope<Order>>('/orders', payload)
  return res.data.data
}

export async function listOrders(params?: {
  customer_id?: string
  status?: string
}): Promise<Order[]> {
  const res = await apiClient.get<SuccessEnvelope<Order[]>>('/orders', { params })
  return res.data.data
}

export async function getOrder(id: string): Promise<Order> {
  const res = await apiClient.get<SuccessEnvelope<Order>>(`/orders/${id}`)
  return res.data.data
}

export async function updateOrderStatus(id: string, status: string): Promise<Order> {
  const res = await apiClient.patch<SuccessEnvelope<Order>>(`/orders/${id}/status`, { status })
  return res.data.data
}

export async function approveOrder(id: string): Promise<Order> {
  const res = await apiClient.post<SuccessEnvelope<Order>>(`/orders/${id}/approve`)
  return res.data.data
}

export async function dispatchOrder(id: string): Promise<Order> {
  const res = await apiClient.post<SuccessEnvelope<Order>>(`/orders/${id}/dispatch`)
  return res.data.data
}

export async function cancelOrder(id: string): Promise<Order> {
  const res = await apiClient.post<SuccessEnvelope<Order>>(`/orders/${id}/cancel`)
  return res.data.data
}
