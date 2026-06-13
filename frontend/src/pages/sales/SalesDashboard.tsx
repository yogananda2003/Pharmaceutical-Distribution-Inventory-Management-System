import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listOrders } from '../../api/orders'
import { listCustomers } from '../../api/customers'
import { OrderStatusBadge } from '../../components/OrderStatusBadge'

export function SalesDashboard() {
  const { data: orders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ['orders'],
    queryFn: () => listOrders(),
  })

  const { data: customers = [], isLoading: customersLoading } = useQuery({
    queryKey: ['customers'],
    queryFn: listCustomers,
  })

  const pending = orders.filter((o) =>
    ['placed', 'approved', 'allocated', 'picked', 'packed'].includes(o.status),
  )
  const dispatched = orders.filter((o) => o.status === 'dispatched')

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-slate-900">Sales Dashboard</h2>

      {/* Summary cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500">Total Customers</p>
          <p className="mt-1 text-2xl font-bold text-slate-900">
            {customersLoading ? '…' : customers.length}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500">Pending Orders</p>
          <p className="mt-1 text-2xl font-bold text-amber-600">
            {ordersLoading ? '…' : pending.length}
          </p>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500">Dispatched</p>
          <p className="mt-1 text-2xl font-bold text-indigo-600">
            {ordersLoading ? '…' : dispatched.length}
          </p>
        </div>
      </div>

      {/* Quick links */}
      <div className="flex gap-3">
        <Link
          to="/sales/orders"
          className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Manage Orders
        </Link>
        <Link
          to="/sales/customers"
          className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          Customer List
        </Link>
        <Link
          to="/customer/search"
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
        >
          + New Order
        </Link>
      </div>

      {/* Recent orders */}
      <div>
        <h3 className="mb-2 text-sm font-medium text-slate-700">Recent Orders</h3>
        {ordersLoading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : orders.length === 0 ? (
          <p className="text-sm text-slate-500">No orders yet.</p>
        ) : (
          <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase text-slate-500">
                <tr>
                  <th className="px-4 py-3 text-left">Order #</th>
                  <th className="px-4 py-3 text-left">Date</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.slice(0, 5).map((o) => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-slate-900">{o.order_number}</td>
                    <td className="px-4 py-3 text-slate-600">{o.order_date}</td>
                    <td className="px-4 py-3">
                      <OrderStatusBadge status={o.status} />
                    </td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      ₹{Number(o.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
