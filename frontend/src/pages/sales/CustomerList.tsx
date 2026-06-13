import { useQuery } from '@tanstack/react-query'
import { listCustomers } from '../../api/customers'

export function CustomerList() {
  const { data: customers = [], isLoading, error } = useQuery({
    queryKey: ['customers'],
    queryFn: listCustomers,
  })

  if (isLoading) return <p className="text-sm text-slate-500">Loading customers…</p>
  if (error) return <p className="text-sm text-red-600">Failed to load customers.</p>

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-900">Customers</h2>

      {customers.length === 0 ? (
        <p className="text-sm text-slate-500">No customers found.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Code</th>
                <th className="px-4 py-3 text-left">Business Name</th>
                <th className="px-4 py-3 text-left">Email</th>
                <th className="px-4 py-3 text-left">Phone</th>
                <th className="px-4 py-3 text-right">Credit Limit</th>
                <th className="px-4 py-3 text-left">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {customers.map((c) => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-slate-600">{c.customer_code}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{c.business_name}</td>
                  <td className="px-4 py-3 text-slate-500">{c.email ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-500">{c.phone ?? '—'}</td>
                  <td className="px-4 py-3 text-right text-slate-700">
                    ₹{Number(c.credit_limit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        c.status === 'active'
                          ? 'bg-emerald-100 text-emerald-700'
                          : 'bg-red-100 text-red-700'
                      }`}
                    >
                      {c.status}
                    </span>
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
