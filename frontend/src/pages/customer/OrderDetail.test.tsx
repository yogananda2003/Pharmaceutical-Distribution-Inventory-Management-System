import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { OrderDetail } from './OrderDetail'
import * as ordersApi from '../../api/orders'
import * as invoicesApi from '../../api/invoices'

const ORDER = {
  id: 'ord1',
  order_number: 'ORD-001',
  customer_id: 'c1',
  order_date: '2026-06-01',
  status: 'dispatched',
  total_amount: '500.00',
  notes: null,
  items: [
    { id: 'i1', medicine_id: 'm1', medicine_name: 'Paracetamol 500mg', quantity: 5, unit_price: '100.00', discount: '0.00', tax_amount: '0.00', line_total: '500.00' },
  ],
}

const INVOICE = {
  id: 'inv1',
  invoice_number: 'INV-2026-001',
  order_id: 'ord1',
  customer_id: 'c1',
  invoice_date: '2026-06-02',
  due_date: '2026-07-02',
  status: 'pending',
  subtotal: '500.00',
  tax_amount: '0.00',
  discount_amount: '0.00',
  total_amount: '500.00',
  notes: null,
  lines: [],
}

function renderOrderDetail(orderId = 'ord1') {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[`/customer/orders/${orderId}`]}>
        <Routes>
          <Route path="/customer/orders/:id" element={<OrderDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('OrderDetail', () => {
  beforeEach(() => {
    vi.spyOn(ordersApi, 'getOrder').mockResolvedValue(ORDER)
    vi.spyOn(invoicesApi, 'getInvoiceByOrder').mockResolvedValue(INVOICE)
  })

  it('shows order number after load', async () => {
    renderOrderDetail()
    expect(await screen.findByText(/ORD-001/)).toBeInTheDocument()
  })

  it('shows status badge', async () => {
    renderOrderDetail()
    expect(await screen.findByText('Dispatched')).toBeInTheDocument()
  })

  it('shows order items', async () => {
    renderOrderDetail()
    expect(await screen.findByText('Paracetamol 500mg')).toBeInTheDocument()
  })

  it('shows invoice number', async () => {
    renderOrderDetail()
    expect(await screen.findByText('INV-2026-001')).toBeInTheDocument()
  })

  it('shows "no invoice" when invoice fetch returns error', async () => {
    vi.spyOn(invoicesApi, 'getInvoiceByOrder').mockRejectedValue(new Error('404'))
    renderOrderDetail()
    expect(await screen.findByText(/ORD-001/)).toBeInTheDocument()
    expect(screen.getByText(/no invoice generated/i)).toBeInTheDocument()
  })
})
