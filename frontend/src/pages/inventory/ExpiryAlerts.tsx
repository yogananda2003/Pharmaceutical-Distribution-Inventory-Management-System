import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { getExpiryDashboard, getExpiredBatches, getNearExpiryBatches } from '../../api/expiry'
import type { BatchExpiryInfo } from '../../api/expiry'

const ALERT_STYLES: Record<string, string> = {
  critical: 'bg-red-100 text-red-700',
  warning:  'bg-amber-100 text-amber-700',
  watch:    'bg-yellow-100 text-yellow-700',
  expired:  'bg-slate-200 text-slate-600',
}

type Tab = 'expired' | 30 | 60 | 90

function BatchTable({ batches, emptyMsg }: { batches: BatchExpiryInfo[]; emptyMsg: string }) {
  if (batches.length === 0) return <p className="py-4 text-sm text-slate-400">{emptyMsg}</p>
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-xs uppercase text-slate-500">
          <tr>
            <th className="px-4 py-3 text-left">Medicine</th>
            <th className="px-4 py-3 text-left">Batch #</th>
            <th className="px-4 py-3 text-left">Warehouse</th>
            <th className="px-4 py-3 text-left">Expiry Date</th>
            <th className="px-4 py-3 text-right">Days</th>
            <th className="px-4 py-3 text-right">Available</th>
            <th className="px-4 py-3 text-right">Reserved</th>
            <th className="px-4 py-3 text-left">Alert</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {batches.map(b => (
            <tr key={b.batch_id} className="hover:bg-slate-50">
              <td className="px-4 py-3">
                <div className="font-medium text-slate-900">{b.medicine_name}</div>
                <div className="text-xs text-slate-400">{b.medicine_code}</div>
              </td>
              <td className="px-4 py-3 font-mono text-xs text-slate-600">{b.batch_number}</td>
              <td className="px-4 py-3 text-slate-500">{b.warehouse_name}</td>
              <td className="px-4 py-3 text-slate-600">{b.expiry_date}</td>
              <td className={`px-4 py-3 text-right font-bold ${b.days_to_expiry < 0 ? 'text-red-600' : b.days_to_expiry <= 30 ? 'text-red-500' : b.days_to_expiry <= 60 ? 'text-amber-600' : 'text-yellow-600'}`}>
                {b.days_to_expiry < 0 ? `${Math.abs(b.days_to_expiry)}d ago` : `${b.days_to_expiry}d`}
              </td>
              <td className="px-4 py-3 text-right text-emerald-700 font-medium">{b.quantity_available}</td>
              <td className="px-4 py-3 text-right text-indigo-600">{b.quantity_reserved}</td>
              <td className="px-4 py-3">
                <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${ALERT_STYLES[b.alert_level] ?? 'bg-slate-100 text-slate-500'}`}>
                  {b.alert_level}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ExpiryAlerts() {
  const [tab, setTab] = useState<Tab>(30)

  const { data: dashboard } = useQuery({
    queryKey: ['expiry-dashboard'],
    queryFn: getExpiryDashboard,
  })

  const { data: expiredBatches = [], isLoading: expiredLoading } = useQuery({
    queryKey: ['expiry-expired'],
    queryFn: getExpiredBatches,
    enabled: tab === 'expired',
  })

  const { data: nearExpiry = [], isLoading: nearLoading } = useQuery({
    queryKey: ['expiry-near', tab],
    queryFn: () => getNearExpiryBatches(tab as number),
    enabled: tab !== 'expired',
  })

  const TABS: { id: Tab; label: string; count?: number; color: string }[] = [
    { id: 30,        label: 'Expiring in 30 days', count: dashboard?.expiring_within_30d, color: 'text-red-600' },
    { id: 60,        label: 'Expiring in 60 days', count: dashboard?.expiring_within_60d, color: 'text-amber-600' },
    { id: 90,        label: 'Expiring in 90 days', count: dashboard?.expiring_within_90d, color: 'text-yellow-600' },
    { id: 'expired', label: 'Already Expired',      count: dashboard?.expired_count,       color: 'text-slate-500' },
  ]

  const isLoading = tab === 'expired' ? expiredLoading : nearLoading
  const batches   = tab === 'expired' ? expiredBatches : nearExpiry

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-slate-900">Expiry Alerts</h2>

      {/* Dashboard summary cards */}
      {dashboard && (
        <div className="grid gap-3 sm:grid-cols-4">
          {TABS.map(t => (
            <button key={String(t.id)} onClick={() => setTab(t.id)}
              className={`rounded-xl border p-4 text-left transition-colors ${tab === t.id ? 'border-indigo-300 bg-indigo-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}>
              <p className="text-xs text-slate-500">{t.label}</p>
              <p className={`mt-1 text-2xl font-bold ${t.color}`}>{t.count ?? '…'}</p>
            </button>
          ))}
        </div>
      )}

      {/* Tab row */}
      <div className="flex gap-1 border-b border-slate-200">
        {TABS.map(t => (
          <button key={String(t.id)} onClick={() => setTab(t.id)}
            className={`px-4 py-2 text-sm font-medium transition-colors ${tab === t.id ? 'border-b-2 border-indigo-600 text-indigo-700' : 'text-slate-500 hover:text-slate-700'}`}>
            {tab === 'expired' && t.id === 'expired' ? 'Expired' : t.id === 'expired' ? 'Expired' : `${t.id}d`}
          </button>
        ))}
      </div>

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : (
        <BatchTable
          batches={batches}
          emptyMsg={tab === 'expired' ? 'No expired batches.' : `No batches expiring within ${tab} days.`}
        />
      )}
    </div>
  )
}
