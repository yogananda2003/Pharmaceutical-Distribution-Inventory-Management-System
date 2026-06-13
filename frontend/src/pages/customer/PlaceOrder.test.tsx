import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { PlaceOrder } from './PlaceOrder'
import * as customersApi from '../../api/customers'
import * as ordersApi from '../../api/orders'

const CUSTOMERS = [
  { id: 'c1', customer_code: 'CUST001', business_name: 'Acme Pharma', credit_limit: '100000', status: 'active', email: null, phone: null },
]

const CART = [
  { medicine: { id: 'm1', name: 'Paracetamol 500mg', code: 'MED001', generic_name: '', manufacturer: '', dosage_form: '', strength: '', unit_type: '' }, quantity: 2, unitPrice: '50.00' },
]

function renderPlaceOrder(state?: object) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[{ pathname: '/customer/order/new', state: state ?? { cart: CART } }]}>
        <Routes>
          <Route path="/customer/order/new" element={<PlaceOrder />} />
          <Route path="/customer/orders/:id" element={<div>Order success</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('PlaceOrder', () => {
  beforeEach(() => {
    vi.spyOn(customersApi, 'listCustomers').mockResolvedValue(CUSTOMERS)
    vi.spyOn(ordersApi, 'createOrder').mockResolvedValue({
      id: 'ord1',
      order_number: 'ORD-001',
      customer_id: 'c1',
      order_date: '2026-06-12',
      status: 'placed',
      total_amount: '100.00',
      notes: null,
      items: [],
    })
  })

  it('shows cart items from location state', () => {
    renderPlaceOrder()
    expect(screen.getByText('Paracetamol 500mg')).toBeInTheDocument()
  })

  it('shows empty cart message when no cart state', () => {
    renderPlaceOrder({ cart: [] })
    expect(screen.getByText(/no items in cart/i)).toBeInTheDocument()
  })

  it('shows validation error when customer not selected', async () => {
    renderPlaceOrder()
    await userEvent.click(screen.getByRole('button', { name: /place order/i }))
    expect(await screen.findByText(/select a customer/i)).toBeInTheDocument()
  })

  it('submits order and navigates to order detail', async () => {
    renderPlaceOrder()

    // Wait for customer options to load
    const option = await screen.findByRole('option', { name: /Acme Pharma/i })
    const select = option.closest('select')!
    await userEvent.selectOptions(select, 'c1')
    await userEvent.click(screen.getByRole('button', { name: /place order/i }))

    expect(await screen.findByText('Order success')).toBeInTheDocument()
    expect(ordersApi.createOrder).toHaveBeenCalledTimes(1)
  })
})
