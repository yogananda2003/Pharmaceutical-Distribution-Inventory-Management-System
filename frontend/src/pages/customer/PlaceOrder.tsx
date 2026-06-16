import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { listCustomers } from '../../api/customers'
import { createOrder } from '../../api/orders'
import { extractApiError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'

interface CartItem {
  medicine: { id: string; name: string; code: string; strength?: string }
  quantity: number
  unitPrice: string
}

export function PlaceOrder() {
  const navigate = useNavigate()
  const location = useLocation()
  const qc = useQueryClient()
  const { userId } = useAuth()

  const cart: CartItem[] = (location.state as { cart?: CartItem[] })?.cart ?? []

  const [customerId, setCustomerId] = useState('')
  const [orderDate, setOrderDate] = useState(new Date().toISOString().slice(0, 10))
  const [notes, setNotes] = useState('')
  const [apiError, setApiError] = useState<string | null>(null)

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers(),
  })

  const total = cart.reduce((sum, c) => sum + c.quantity * (parseFloat(c.unitPrice) || 0), 0)

  const { mutateAsync, isPending } = useMutation({
    mutationFn: createOrder,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }),
  })

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (cart.length === 0) { setApiError('Cart is empty. Go back and add medicines.'); return }
    if (!customerId) { setApiError('Please select a customer.'); return }
    setApiError(null)
    try {
      const order = await mutateAsync({
        customer_id: customerId,
        sales_rep_id: userId ?? undefined,
        order_date: orderDate,
        notes: notes.trim() || undefined,
        items: cart.map(c => ({
          medicine_id: c.medicine.id,
          quantity: c.quantity,
          unit_price: parseFloat(c.unitPrice).toFixed(2) || '0.00',
          discount: '0.00',
          tax_amount: '0.00',
        })),
      })
      navigate(`/customer/orders/${order.id}`, { replace: true })
    } catch (err) {
      setApiError(extractApiError(err, 'Failed to place order. Please try again.'))
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div className="flex items-center gap-3">
        <button onClick={() => navigate(-1)} className="text-sm text-indigo-600 hover:underline">← Back</button>
        <h2 className="text-lg font-semibold text-slate-900">Place Order</h2>
      </div>

      {/* Cart summary */}
      {cart.length === 0 ? (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
          Cart is empty.{' '}
          <button onClick={() => navigate('/customer/search')} className="font-medium underline">
            Browse products
          </button>
        </div>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-5 py-3">
            <h3 className="text-sm font-semibold text-slate-800">Order Items ({cart.length})</h3>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-2 text-left">Medicine</th>
                <th className="px-4 py-2 text-right">Qty</th>
                <th className="px-4 py-2 text-right">Unit Price</th>
                <th className="px-4 py-2 text-right">Line Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {cart.map(c => (
                <tr key={c.medicine.id}>
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-slate-900">{c.medicine.name}</div>
                    <div className="text-xs text-slate-400">{c.medicine.code}{c.medicine.strength ? ` · ${c.medicine.strength}` : ''}</div>
                  </td>
                  <td className="px-4 py-2.5 text-right text-slate-700">{c.quantity}</td>
                  <td className="px-4 py-2.5 text-right text-slate-700">₹{parseFloat(c.unitPrice || '0').toFixed(2)}</td>
                  <td className="px-4 py-2.5 text-right font-medium text-slate-900">
                    ₹{(c.quantity * (parseFloat(c.unitPrice) || 0)).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t border-slate-200 bg-slate-50">
                <td colSpan={3} className="px-4 py-3 text-right font-semibold text-slate-700">Total</td>
                <td className="px-4 py-3 text-right font-bold text-indigo-700">
                  ₹{total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                </td>
              </tr>
            </tfoot>
          </table>
        </div>
      )}

      <form onSubmit={onSubmit} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Customer *</label>
            <select value={customerId} onChange={e => setCustomerId(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none">
              <option value="">Select customer…</option>
              {customers.map(c => (
                <option key={c.id} value={c.id}>
                  {c.business_name} ({c.customer_code})
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-slate-700">Order Date *</label>
            <input type="date" value={orderDate} onChange={e => setOrderDate(e.target.value)}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none" />
          </div>
        </div>

        <div>
          <label className="mb-1 block text-sm font-medium text-slate-700">Notes (optional)</label>
          <textarea
            rows={3}
            value={notes}
            onChange={e => setNotes(e.target.value)}
            placeholder="Delivery instructions, special requirements, etc."
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none resize-none"
          />
        </div>

        {apiError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{apiError}</p>
        )}

        <div className="flex gap-3">
          <button type="button" onClick={() => navigate(-1)}
            className="flex-1 rounded-lg border border-slate-300 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Back
          </button>
          <button type="submit" disabled={isPending || cart.length === 0}
            className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
            {isPending ? 'Placing…' : `Place Order — ₹${total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`}
          </button>
        </div>
      </form>
    </div>
  )
}
