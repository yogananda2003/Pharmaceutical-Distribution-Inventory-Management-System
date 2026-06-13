import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { SalesDashboard } from './SalesDashboard'
import * as ordersApi from '../../api/orders'
import * as customersApi from '../../api/customers'

const ORDERS = [
  { id: 'o1', order_number: 'ORD-001', customer_id: 'c1', order_date: '2026-06-01', status: 'placed', total_amount: '200.00', notes: null, items: [] },
  { id: 'o2', order_number: 'ORD-002', customer_id: 'c1', order_date: '2026-06-05', status: 'dispatched', total_amount: '350.00', notes: null, items: [] },
]

const CUSTOMERS = [
  { id: 'c1', customer_code: 'CUST001', business_name: 'Acme Pharma', credit_limit: '100000', status: 'active', email: null, phone: null },
  { id: 'c2', customer_code: 'CUST002', business_name: 'Beta Medical', credit_limit: '50000', status: 'active', email: null, phone: null },
]

function renderSalesDashboard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SalesDashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('SalesDashboard', () => {
  beforeEach(() => {
    vi.spyOn(ordersApi, 'listOrders').mockResolvedValue(ORDERS)
    vi.spyOn(customersApi, 'listCustomers').mockResolvedValue(CUSTOMERS)
  })

  it('shows dashboard heading', () => {
    renderSalesDashboard()
    expect(screen.getByText(/sales dashboard/i)).toBeInTheDocument()
  })

  it('shows total customers count', async () => {
    renderSalesDashboard()
    expect(await screen.findByText('2')).toBeInTheDocument()
  })

  it('shows pending orders count', async () => {
    renderSalesDashboard()
    // 1 order in 'placed' status = 1 pending
    await screen.findByText('2') // wait for data load
    const cards = screen.getAllByText('1')
    expect(cards.length).toBeGreaterThanOrEqual(1)
  })

  it('shows recent orders table', async () => {
    renderSalesDashboard()
    expect(await screen.findByText('ORD-001')).toBeInTheDocument()
  })

  it('shows navigation links', () => {
    renderSalesDashboard()
    expect(screen.getByRole('link', { name: /manage orders/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /customer list/i })).toBeInTheDocument()
  })
})
