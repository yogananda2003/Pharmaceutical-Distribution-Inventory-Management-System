import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { listOrders } from '../../api/orders'
import { listCustomers } from '../../api/customers'
import { listBatches } from '../../api/inventory'
import { getExpiryDashboard } from '../../api/expiry'
import { OrderStatusBadge } from '../../components/OrderStatusBadge'
import { useAuth } from '../../contexts/AuthContext'

export function SalesDashboard() {
  const { role } = useAuth()

  const isAdmin     = role === 'admin'
  const isInventory = role === 'admin' || role === 'inventory_manager'
  const isWarehouse = role === 'warehouse_staff'

  const { data: orders = [], isLoading: ordersLoading } = useQuery({
    queryKey: ['orders'],
    queryFn: () => listOrders(),
  })

  const { data: customers = [] } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers(),
    enabled: !isWarehouse,
  })

  const { data: batches = [] } = useQuery({
    queryKey: ['inventory-batches'],
    queryFn: () => listBatches({ active_only: true }),
    enabled: isInventory || isWarehouse,
  })

  const { data: expiry } = useQuery({
    queryKey: ['expiry-dashboard'],
    queryFn: getExpiryDashboard,
    enabled: isInventory || isWarehouse,
  })

  // Order metrics
  const placed    = orders.filter(o => o.status === 'placed').length
  const approved  = orders.filter(o => o.status === 'approved').length
  const packed    = orders.filter(o => o.status === 'packed').length
  const dispatched = orders.filter(o => o.status === 'dispatched').length
  const completed  = orders.filter(o => ['delivered', 'completed'].includes(o.status)).length

  const totalRevenue = orders
    .filter(o => ['dispatched', 'delivered', 'completed'].includes(o.status))
    .reduce((sum, o) => sum + Number(o.total_amount), 0)

  // Stock metrics
  const totalBatches  = batches.length
  const lowStockCount = batches.filter(b => b.quantity_available < 10).length

  const ROLE_TITLE: Record<string, string> = {
    admin:                 'Admin Dashboard',
    inventory_manager:     'Inventory Dashboard',
    sales_representative:  'Sales Dashboard',
    warehouse_staff:       'Warehouse Dashboard',
  }

  return (
    <div className="space-y-6">
      <h2 className="text-lg font-semibold text-slate-900">{ROLE_TITLE[role ?? ''] ?? 'Dashboard'}</h2>

      {/* ── KPI Cards ──────────────────────────────────────────────── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

        {/* Orders waiting approval */}
        {!isWarehouse && (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Awaiting Approval</p>
            <p className="mt-1 text-2xl font-bold text-amber-600">{ordersLoading ? '…' : placed}</p>
            <Link to="/sales/orders?status=placed" className="mt-2 block text-xs text-indigo-600 hover:underline">View →</Link>
          </div>
        )}

        {/* Ready to dispatch */}
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500">Ready to Dispatch</p>
          <p className="mt-1 text-2xl font-bold text-indigo-600">{ordersLoading ? '…' : packed}</p>
          <Link to="/sales/orders?status=packed" className="mt-2 block text-xs text-indigo-600 hover:underline">View →</Link>
        </div>

        {/* Dispatched */}
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <p className="text-xs text-slate-500">Dispatched</p>
          <p className="mt-1 text-2xl font-bold text-emerald-600">{ordersLoading ? '…' : dispatched}</p>
        </div>

        {/* Customers or Completed */}
        {!isWarehouse ? (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Total Customers</p>
            <p className="mt-1 text-2xl font-bold text-slate-900">{customers.length}</p>
            <Link to="/sales/customers" className="mt-2 block text-xs text-indigo-600 hover:underline">Manage →</Link>
          </div>
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Completed Orders</p>
            <p className="mt-1 text-2xl font-bold text-slate-900">{ordersLoading ? '…' : completed}</p>
          </div>
        )}
      </div>

      {/* ── Second row: inventory + expiry ─────────────────────────── */}
      {(isInventory || isWarehouse) && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Active Batches</p>
            <p className="mt-1 text-2xl font-bold text-slate-900">{totalBatches}</p>
            <Link to="/inventory/stock" className="mt-2 block text-xs text-indigo-600 hover:underline">View stock →</Link>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Low Stock ({"<"}10 units)</p>
            <p className={`mt-1 text-2xl font-bold ${lowStockCount > 0 ? 'text-red-600' : 'text-emerald-600'}`}>{lowStockCount}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Expiring in 30 days</p>
            <p className={`mt-1 text-2xl font-bold ${(expiry?.expiring_within_30d ?? 0) > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
              {expiry ? expiry.expiring_within_30d : '…'}
            </p>
            <Link to="/inventory/expiry" className="mt-2 block text-xs text-indigo-600 hover:underline">View alerts →</Link>
          </div>
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <p className="text-xs text-slate-500">Expired Stock</p>
            <p className={`mt-1 text-2xl font-bold ${(expiry?.expired_count ?? 0) > 0 ? 'text-red-700' : 'text-emerald-600'}`}>
              {expiry ? expiry.expired_count : '…'}
            </p>
            <Link to="/inventory/expiry" className="mt-2 block text-xs text-indigo-600 hover:underline">Review →</Link>
          </div>
        </div>
      )}

      {/* ── Revenue card (admin / sales only) ──────────────────────── */}
      {!isWarehouse && isAdmin && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4 flex items-center justify-between">
          <div>
            <p className="text-xs text-emerald-700">Revenue (dispatched + delivered)</p>
            <p className="mt-0.5 text-3xl font-bold text-emerald-800">
              ₹{totalRevenue.toLocaleString('en-IN', { minimumFractionDigits: 2 })}
            </p>
          </div>
          <div className="text-right text-sm text-emerald-700">
            <div>{approved} approved</div>
            <div>{completed} completed</div>
          </div>
        </div>
      )}

      {/* ── Quick actions ───────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-3">
        <Link to="/sales/orders"
          className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
          Manage Orders
        </Link>
        {!isWarehouse && (
          <Link to="/sales/customers"
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
            Customers
          </Link>
        )}
        {isInventory && (
          <>
            <Link to="/inventory/stock"
              className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Stock / Batches
            </Link>
            <Link to="/inventory/expiry"
              className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-700 hover:bg-amber-100">
              Expiry Alerts
            </Link>
          </>
        )}
        {!isWarehouse && (
          <Link to="/customer/search"
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
            + New Order
          </Link>
        )}
      </div>

      {/* ── Recent orders ───────────────────────────────────────────── */}
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
                  {!isWarehouse && <th className="px-4 py-3 text-left">Customer</th>}
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3 text-right">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {orders.slice(0, 8).map(o => (
                  <tr key={o.id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-mono text-slate-900">
                      <Link to={`/customer/orders/${o.id}`} className="text-indigo-600 hover:underline">{o.order_number}</Link>
                    </td>
                    <td className="px-4 py-3 text-slate-600">{o.order_date}</td>
                    {!isWarehouse && (
                      <td className="px-4 py-3 text-slate-700">
                        {o.customer_name ?? customers.find(c => c.id === o.customer_id)?.business_name ?? '—'}
                      </td>
                    )}
                    <td className="px-4 py-3"><OrderStatusBadge status={o.status} /></td>
                    <td className="px-4 py-3 text-right text-slate-700">
                      ₹{Number(o.total_amount).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {orders.length > 8 && (
              <div className="border-t border-slate-100 px-4 py-2 text-center">
                <Link to="/sales/orders" className="text-xs text-indigo-600 hover:underline">View all {orders.length} orders →</Link>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
