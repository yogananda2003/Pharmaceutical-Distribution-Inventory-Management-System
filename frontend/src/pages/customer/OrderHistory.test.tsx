import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { OrderHistory } from './OrderHistory'
import * as ordersApi from '../../api/orders'
import { AuthContext } from '../../contexts/AuthContext'

const AUTH_VALUE = {
  token: 'tok',
  role: 'sales_representative',
  userId: 'u1',
  isAuthenticated: true,
  login: vi.fn(),
  logout: vi.fn(),
}

const ORDERS = [
  { id: 'o1', order_number: 'ORD-001', customer_id: 'c1', order_date: '2026-06-01', status: 'placed', total_amount: '200.00', notes: null, items: [] },
  { id: 'o2', order_number: 'ORD-002', customer_id: 'c1', order_date: '2026-06-05', status: 'completed', total_amount: '350.00', notes: null, items: [] },
]

function renderOrderHistory() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <AuthContext.Provider value={AUTH_VALUE}>
          <OrderHistory />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('OrderHistory', () => {
  beforeEach(() => {
    vi.spyOn(ordersApi, 'listOrders').mockResolvedValue(ORDERS)
  })

  it('renders order history heading', async () => {
    renderOrderHistory()
    expect(await screen.findByRole('heading', { name: /order history/i })).toBeInTheDocument()
  })

  it('shows order rows after loading', async () => {
    renderOrderHistory()
    expect(await screen.findByText('ORD-001')).toBeInTheDocument()
    expect(screen.getByText('ORD-002')).toBeInTheDocument()
  })

  it('shows status badges', async () => {
    renderOrderHistory()
    expect(await screen.findByText('Placed')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
  })

  it('shows new order link', async () => {
    renderOrderHistory()
    expect(await screen.findByRole('link', { name: /new order/i })).toBeInTheDocument()
  })

  it('shows empty message when no orders', async () => {
    vi.spyOn(ordersApi, 'listOrders').mockResolvedValue([])
    renderOrderHistory()
    expect(await screen.findByText(/no orders yet/i)).toBeInTheDocument()
  })
})
