import { apiClient, type SuccessEnvelope } from './client'

export interface InvoiceLine {
  id: string
  medicine_id: string
  description: string
  quantity: number
  unit_price: string
  discount: string
  tax_amount: string
  line_total: string
}

export interface Invoice {
  id: string
  invoice_number: string
  order_id: string
  customer_id: string
  invoice_date: string
  due_date: string | null
  status: string
  subtotal: string
  tax_amount: string
  discount_amount: string
  total_amount: string
  notes: string | null
  lines: InvoiceLine[]
}

export async function listInvoices(params?: { customer_id?: string; status?: string }): Promise<Invoice[]> {
  const res = await apiClient.get<SuccessEnvelope<Invoice[]>>('/invoices', { params })
  return res.data.data
}

export async function getInvoiceByOrder(orderId: string): Promise<Invoice> {
  const res = await apiClient.get<SuccessEnvelope<Invoice>>(`/invoices/order/${orderId}`)
  return res.data.data
}

export async function generateInvoice(orderId: string): Promise<Invoice> {
  const res = await apiClient.post<SuccessEnvelope<Invoice>>('/invoices', { order_id: orderId })
  return res.data.data
}
