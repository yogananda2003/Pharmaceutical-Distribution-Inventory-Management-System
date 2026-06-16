import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { approveOrder, cancelOrder, dispatchOrder, listOrders } from '../../api/orders'
import { listCustomers } from '../../api/customers'
import { OrderStatusBadge } from '../../components/OrderStatusBadge'
import { useAuth } from '../../contexts/AuthContext'
import { extractApiError } from '../../api/client'

const STATUS_OPTIONS = ['', 'placed', 'approved', 'allocated', 'picked', 'packed', 'dispatched', 'delivered', 'completed', 'cancelled']

export function OrderManagement() {
  const qc = useQueryClient()
  const { role } = useAuth()
  const [statusFilter, setStatusFilter] = useState('')
  const [customerFilter, setCustomerFilter] = useState('')
  const [actionError, setActionError] = useState<string | null>(null)

  const isAdmin = role === 'admin' || role === 'inventory_manager'
  const isSales = role === 'admin' || role === 'sales_representative'
  const isWarehouse = role === 'warehouse_staff'

  const { data: orders = [], isLoading } = useQuery({
    queryKey: ['orders', statusFilter, customerFilter],
    queryFn: () => listOrders({
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(customerFilter ? { customer_id: customerFilter } : {}),
    }),
  })

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers(),
    enabled: !isWarehouse,
  })

  function onError(e: unknown) { setActionError(extractApiError(e, 'Action failed.')) }

  const approve = useMutation({ mutationFn: approveOrder, onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }), onError })
  const dispatch = useMutation({ mutationFn: dispatchOrder, onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }), onError })
  const cancel = useMutation({ mutationFn: cancelOrder, onSuccess: () => qc.invalidateQueries({ queryKey: ['orders'] }), onError })

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Order Management</h2>
        {isSales && (
          <Link to="/customer/search"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
            + New Order
          </Link>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3">
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Status</label>
          <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none">
            {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s || 'All'}</option>)}
          </select>
        </div>
        {!isWarehouse && (
          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-500">Customer</label>
            <select value={customerFilter} onChange={e => setCustomerFilter(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm focus:border-indigo-500 focus:outline-none">
              <option value="">All</option>
              {customers.map(c => <option key={c.id} value={c.id}>{c.business_name}</option>)}
            </select>
          </div>
        )}
        {(statusFilter || customerFilter) && (
          <button onClick={() => { setStatusFilter(''); setCustomerFilter('') }}
            className="text-xs text-slate-500 hover:text-red-600">✕ Clear filters</button>
        )}
      </div>

      {actionError && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{actionError}</p>
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading orders…</p>
      ) : orders.length === 0 ? (
        <p className="text-sm text-slate-500">No orders found.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Order #</th>
                <th className="px-4 py-3 text-left">Date</th>
                {!isWarehouse && <th className="px-4 py-3 text-left">Customer</th>}
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-right">Total</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {orders.map(order => {
                const custName = order.customer_name
                  ?? customers.find(c => c.id === order.customer_id)?.business_name
                  ?? order.customer_id
                return (
                  <tr key={order.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono font-medium">
                      <Link to={`/customer/orders/${order.id}`} className="text-indigo-600 hover:underline">
                        {order.order_number}
                      </Link>
                      {order.notes && (
                        <div className="text-xs text-slate-400 mt-0.5 truncate max-w-[120px]" title={order.notes}>
                          📝 {order.notes}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-600">{order.order_date}</td>
                    {!isWarehouse && (
                      <td className="px-4 py-3 text-slate-700 font-medium">{custName}</td>
                    )}
                    <td className="px-4 py-3"><OrderStatusBadge status={order.status} /></td>
                    <td className="px-4 py-3 text-right text-slate-700 font-medium">
                      ₹{Number(order.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex justify-center gap-2">
                        {/* Approve: admin/inventory_manager only */}
                        {isAdmin && order.status === 'placed' && (
                          <button onClick={() => { setActionError(null); approve.mutate(order.id) }}
                            disabled={approve.isPending}
                            className="rounded px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50">
                            Approve
                          </button>
                        )}
                        {/* Dispatch: admin/inventory_manager/warehouse_staff */}
                        {(isAdmin || isWarehouse) && order.status === 'packed' && (
                          <button onClick={() => { setActionError(null); dispatch.mutate(order.id) }}
                            disabled={dispatch.isPending}
                            className="rounded px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-50 disabled:opacity-50">
                            Dispatch
                          </button>
                        )}
                        {/* Cancel: sales roles only (not warehouse) */}
                        {isSales && !['cancelled', 'completed', 'delivered', 'dispatched'].includes(order.status) && (
                          <button onClick={() => { setActionError(null); cancel.mutate(order.id) }}
                            disabled={cancel.isPending}
                            className="rounded px-2 py-1 text-xs font-medium text-red-700 hover:bg-red-50 disabled:opacity-50">
                            Cancel
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
