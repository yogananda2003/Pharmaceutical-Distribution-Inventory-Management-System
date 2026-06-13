import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useLocation, useNavigate } from 'react-router-dom'
import { z } from 'zod'
import { listCustomers } from '../../api/customers'
import { createOrder } from '../../api/orders'

const schema = z.object({
  customer_id: z.string().min(1, 'Select a customer'),
  order_date: z.string().min(1, 'Order date is required'),
})

type FormValues = z.infer<typeof schema>

interface CartItem {
  medicine: { id: string; name: string; code: string }
  quantity: number
  unitPrice: string
}

export function PlaceOrder() {
  const navigate = useNavigate()
  const location = useLocation()
  const queryClient = useQueryClient()
  const cart: CartItem[] = (location.state as { cart?: CartItem[] })?.cart ?? []
  const [apiError, setApiError] = useState<string | null>(null)

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: listCustomers,
  })

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { order_date: new Date().toISOString().slice(0, 10) },
  })

  const { mutateAsync } = useMutation({
    mutationFn: createOrder,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['orders'] })
    },
  })

  async function onSubmit(values: FormValues) {
    if (cart.length === 0) {
      setApiError('Your cart is empty. Go back and add medicines.')
      return
    }
    setApiError(null)
    try {
      const order = await mutateAsync({
        customer_id: values.customer_id,
        order_date: values.order_date,
        items: cart.map((c) => ({
          medicine_id: c.medicine.id,
          quantity: c.quantity,
          unit_price: c.unitPrice || '0.00',
          discount: '0.00',
          tax_amount: '0.00',
        })),
      })
      navigate(`/customer/orders/${order.id}`, { replace: true })
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        'Failed to place order. Please try again.'
      setApiError(msg)
    }
  }

  return (
    <div className="mx-auto max-w-xl space-y-6">
      <h2 className="text-lg font-semibold text-slate-900">Place Order</h2>

      {/* Cart summary */}
      {cart.length === 0 ? (
        <p className="text-sm text-slate-500">
          No items in cart.{' '}
          <button
            onClick={() => navigate('/customer/search')}
            className="text-indigo-600 underline"
          >
            Browse products
          </button>
        </p>
      ) : (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
          <h3 className="mb-2 text-sm font-medium text-slate-700">Order Items</h3>
          <ul className="space-y-1 text-sm text-slate-600">
            {cart.map((c) => (
              <li key={c.medicine.id} className="flex justify-between">
                <span>{c.medicine.name}</span>
                <span>
                  {c.quantity} × ₹{c.unitPrice}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-4">
        <div>
          <label htmlFor="customer_id" className="mb-1 block text-sm font-medium text-slate-700">
            Customer
          </label>
          <select
            id="customer_id"
            {...register('customer_id')}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">Select customer…</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {c.business_name} ({c.customer_code})
              </option>
            ))}
          </select>
          {errors.customer_id && (
            <p className="mt-1 text-xs text-red-600">{errors.customer_id.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="order_date" className="mb-1 block text-sm font-medium text-slate-700">
            Order Date
          </label>
          <input
            id="order_date"
            type="date"
            {...register('order_date')}
            className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          />
          {errors.order_date && (
            <p className="mt-1 text-xs text-red-600">{errors.order_date.message}</p>
          )}
        </div>

        {apiError && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{apiError}</p>
        )}

        <div className="flex gap-3">
          <button
            type="button"
            onClick={() => navigate(-1)}
            className="flex-1 rounded-lg border border-slate-300 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Back
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex-1 rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {isSubmitting ? 'Placing…' : 'Place Order'}
          </button>
        </div>
      </form>
    </div>
  )
}
