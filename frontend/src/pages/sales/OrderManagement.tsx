import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { approveOrder, cancelOrder, dispatchOrder, listOrders } from '../../api/orders'
import { OrderStatusBadge } from '../../components/OrderStatusBadge'

export function OrderManagement() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ['orders', statusFilter],
    queryFn: () => listOrders(statusFilter ? { status: statusFilter } : undefined),
  })

  function onMutationError() {
    setActionError('Action failed. Please try again.')
  }

  const approve = useMutation({ mutationFn: approveOrder, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orders'] }), onError: onMutationError })
  const dispatch = useMutation({ mutationFn: dispatchOrder, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orders'] }), onError: onMutationError })
  const cancel = useMutation({ mutationFn: cancelOrder, onSuccess: () => queryClient.invalidateQueries({ queryKey: ['orders'] }), onError: onMutationError })

  const STATUS_OPTIONS = ['', 'placed', 'approved', 'allocated', 'dispatched', 'completed', 'cancelled']

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Order Management</h2>
        <Link
          to="/customer/search"
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          + New Order
        </Link>
      </div>

      {/* Filter */}
      <div className="flex items-center gap-3">
        <label htmlFor="status-filter" className="text-sm text-slate-600">
          Filter by status:
        </label>
        <select
          id="status-filter"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none"
        >
          {STATUS_OPTIONS.map((s) => (
            <option key={s} value={s}>
              {s || 'All'}
            </option>
          ))}
        </select>
      </div>

      {actionError && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading orders…</p>
      ) : orders.length === 0 ? (
        <p className="text-sm text-slate-500">No orders found.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Order #</th>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right">Total</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {orders.map((order) => (
                <tr key={order.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono font-medium text-slate-900">
                    <Link to={`/customer/orders/${order.id}`} className="text-indigo-600 hover:underline">
                      {order.order_number}
                    </Link>
                  </td>
                  <td className="px-4 py-3 text-slate-600">{order.order_date}</td>
                  <td className="px-4 py-3">
                    <OrderStatusBadge status={order.status} />
                  </td>
                  <td className="px-4 py-3 text-right text-slate-700">
                    ₹{Number(order.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex justify-center gap-2">
                      {order.status === 'placed' && (
                        <button
                          onClick={() => approve.mutate(order.id)}
                          disabled={approve.isPending}
                          className="rounded px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                        >
                          Approve
                        </button>
                      )}
                      {order.status === 'packed' && (
                        <button
                          onClick={() => dispatch.mutate(order.id)}
                          disabled={dispatch.isPending}
                          className="rounded px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50"
                        >
                          Dispatch
                        </button>
                      )}
                      {!['cancelled', 'completed', 'delivered'].includes(order.status) && (
                        <button
                          onClick={() => cancel.mutate(order.id)}
                          disabled={cancel.isPending}
                          className="rounded px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
