import { useQuery } from '@tanstack/react-query'
import { useParams, Link } from 'react-router-dom'
import { getOrder } from '../../api/orders'
import { getInvoiceByOrder } from '../../api/invoices'
import { OrderStatusBadge } from '../../components/OrderStatusBadge'

const STATUS_STEPS = [
  'placed',
  'approved',
  'allocated',
  'picked',
  'packed',
  'dispatched',
  'delivered',
  'completed',
]

export function OrderDetail() {
  const { id } = useParams<{ id: string }>()

  const { data: order, isLoading: orderLoading, error: orderError } = useQuery({
    queryKey: ['orders', id],
    queryFn: () => getOrder(id!),
    enabled: !!id,
  })

  const { data: invoice } = useQuery({
    queryKey: ['invoices', 'by-order', id],
    queryFn: () => getInvoiceByOrder(id!),
    enabled: !!id,
    retry: false,
  })

  if (orderLoading) return <p className="text-sm text-slate-500">Loading order…</p>
  if (orderError || !order) return <p className="text-sm text-red-600">Order not found.</p>

  const currentStepIdx = STATUS_STEPS.indexOf(order.status)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/customer/orders" className="text-sm text-indigo-600 hover:underline">
            ← Orders
          </Link>
          <h2 className="mt-1 text-lg font-semibold text-slate-900">
            Order {order.order_number}
          </h2>
        </div>
        <OrderStatusBadge status={order.status} />
      </div>

      {/* Progress timeline */}
      {order.status !== 'cancelled' && order.status !== 'draft' && (
        <div className="rounded-xl border border-slate-200 bg-white p-4">
          <h3 className="mb-3 text-sm font-medium text-slate-700">Order Progress</h3>
          <div className="flex items-center gap-0">
            {STATUS_STEPS.map((step, idx) => (
              <div key={step} className="flex flex-1 items-center">
                <div
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                    idx <= currentStepIdx
                      ? 'bg-indigo-600 text-white'
                      : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {idx < currentStepIdx ? '✓' : idx + 1}
                </div>
                {idx < STATUS_STEPS.length - 1 && (
                  <div
                    className={`h-0.5 flex-1 ${idx < currentStepIdx ? 'bg-indigo-600' : 'bg-slate-200'}`}
                  />
                )}
              </div>
            ))}
          </div>
          <div className="mt-1 flex">
            {STATUS_STEPS.map((step) => (
              <div key={step} className="flex-1 text-center text-[10px] capitalize text-slate-500">
                {step}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Order details */}
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <h3 className="mb-3 text-sm font-medium text-slate-700">Items</h3>
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-slate-500">
            <tr>
              <th className="pb-2 text-left">Medicine</th>
              <th className="pb-2 text-right">Qty</th>
              <th className="pb-2 text-right">Unit Price</th>
              <th className="pb-2 text-right">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {order.items.map((item) => (
              <tr key={item.id}>
                <td className="py-2 text-slate-700">{item.medicine_name ?? item.medicine_id}</td>
                <td className="py-2 text-right text-slate-600">{item.quantity}</td>
                <td className="py-2 text-right text-slate-600">₹{item.unit_price}</td>
                <td className="py-2 text-right font-medium text-slate-800">
                  ₹
                  {(Number(item.unit_price) * item.quantity).toLocaleString('en-IN', {
                    minimumFractionDigits: 2,
                  })}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={3} className="pt-3 text-right text-sm font-semibold text-slate-700">
                Total
              </td>
              <td className="pt-3 text-right text-sm font-bold text-slate-900">
                ₹
                {Number(order.total_amount).toLocaleString('en-IN', {
                  minimumFractionDigits: 2,
                })}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>

      {/* Invoice section */}
      {invoice ? (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
          <h3 className="mb-3 text-sm font-medium text-emerald-800">Invoice</h3>
          <dl className="grid grid-cols-2 gap-2 text-sm">
            <div>
              <dt className="text-xs text-slate-500">Invoice #</dt>
              <dd className="font-mono font-medium text-slate-900">{invoice.invoice_number}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Status</dt>
              <dd className="capitalize text-slate-700">{invoice.status}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Invoice Date</dt>
              <dd className="text-slate-700">{invoice.invoice_date}</dd>
            </div>
            {invoice.due_date && (
              <div>
                <dt className="text-xs text-slate-500">Due Date</dt>
                <dd className="text-slate-700">{invoice.due_date}</dd>
              </div>
            )}
            <div>
              <dt className="text-xs text-slate-500">Subtotal</dt>
              <dd className="text-slate-700">₹{invoice.subtotal}</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">Total</dt>
              <dd className="font-bold text-emerald-900">₹{invoice.total_amount}</dd>
            </div>
          </dl>
        </div>
      ) : (
        <p className="text-sm text-slate-400">No invoice generated yet.</p>
      )}
    </div>
  )
}
