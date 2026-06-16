import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { adjustStock, damageStock, listBatches, stockIn } from '../../api/inventory'
import type { InventoryBatch } from '../../api/inventory'

type Action = 'stock-in' | 'adjust' | 'damage'

interface ActionState {
  batch: InventoryBatch
  type: Action
  quantity: string
  reason: string
}

const BATCH_STATUS_STYLES: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  exhausted: 'bg-slate-100 text-slate-500',
  expired: 'bg-red-100 text-red-700',
}

export function StockBatches() {
  const qc = useQueryClient()
  const [action, setAction] = useState<ActionState | null>(null)
  const [error, setError] = useState<string | null>(null)

  const { data: batches = [], isLoading } = useQuery({
    queryKey: ['inventory-batches'],
    queryFn: () => listBatches({ active_only: false }),
  })

  const mutate = useMutation({
    mutationFn: async () => {
      if (!action) return
      const qty = parseInt(action.quantity)
      if (isNaN(qty) || qty <= 0) throw new Error('Enter a positive quantity')
      if (action.type === 'stock-in') return stockIn(action.batch.id, qty)
      if (action.type === 'adjust') return adjustStock(action.batch.id, qty, action.reason)
      return damageStock(action.batch.id, qty, action.reason)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory-batches'] })
      setAction(null)
      setError(null)
    },
    onError: (e: Error) => setError(e.message || 'Action failed.'),
  })

  const ACTION_LABEL: Record<Action, string> = {
    'stock-in': 'Add Stock',
    'adjust': 'Adjust Quantity',
    'damage': 'Write Off Damaged',
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-900">Stock / Inventory Batches</h2>

      {/* Action panel */}
      {action && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h3 className="mb-1 text-sm font-semibold text-amber-900">{ACTION_LABEL[action.type]}</h3>
          <p className="mb-3 text-xs text-amber-700">
            Batch: <strong>{action.batch.batch_number}</strong> — {action.batch.medicine_name ?? action.batch.medicine_id}
            &nbsp;| Available: <strong>{action.batch.quantity_available}</strong>
          </p>
          <div className="flex flex-wrap gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Quantity *</label>
              <input
                type="number" min={1} value={action.quantity}
                onChange={e => setAction(a => a ? { ...a, quantity: e.target.value } : a)}
                className="w-28 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:border-amber-500"
              />
            </div>
            {action.type !== 'stock-in' && (
              <div className="flex-1 min-w-[200px]">
                <label className="mb-1 block text-xs font-medium text-slate-700">Reason *</label>
                <input
                  value={action.reason}
                  onChange={e => setAction(a => a ? { ...a, reason: e.target.value } : a)}
                  placeholder={action.type === 'adjust' ? 'Physical count correction' : 'Expired / broken'}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:border-amber-500"
                />
              </div>
            )}
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => mutate.mutate()}
              disabled={mutate.isPending}
              className="rounded-lg bg-amber-600 px-5 py-2 text-sm font-semibold text-white hover:bg-amber-700 disabled:opacity-50"
            >
              {mutate.isPending ? 'Saving…' : 'Confirm'}
            </button>
            <button onClick={() => { setAction(null); setError(null) }}
              className="rounded-lg border border-slate-300 px-5 py-2 text-sm text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : batches.length === 0 ? (
        <p className="text-sm text-slate-500">No batches. Receive goods from a Purchase Order first.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Batch #</th>
                <th className="px-4 py-3 text-left">Medicine</th>
                <th className="px-4 py-3 text-left">Warehouse</th>
                <th className="px-4 py-3 text-left">Expiry</th>
                <th className="px-4 py-3 text-right">Available</th>
                <th className="px-4 py-3 text-right">Reserved</th>
                <th className="px-4 py-3 text-right">Damaged</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {batches.map(b => (
                <tr key={b.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{b.batch_number}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{b.medicine_name ?? b.medicine_id}</td>
                  <td className="px-4 py-3 text-slate-500">{b.warehouse_name ?? b.warehouse_id}</td>
                  <td className="px-4 py-3 text-slate-600">{b.expiry_date}</td>
                  <td className="px-4 py-3 text-right font-semibold text-emerald-700">{b.quantity_available}</td>
                  <td className="px-4 py-3 text-right text-indigo-600">{b.quantity_reserved}</td>
                  <td className="px-4 py-3 text-right text-red-600">{b.quantity_damaged}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${BATCH_STATUS_STYLES[b.status] ?? 'bg-slate-100 text-slate-500'}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex justify-center gap-2">
                      <button onClick={() => setAction({ batch: b, type: 'stock-in', quantity: '', reason: '' })}
                        className="rounded px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50">+Stock</button>
                      <button onClick={() => setAction({ batch: b, type: 'adjust', quantity: '', reason: '' })}
                        className="rounded px-2 py-1 text-xs text-amber-700 hover:bg-amber-50">Adjust</button>
                      <button onClick={() => setAction({ batch: b, type: 'damage', quantity: '', reason: '' })}
                        className="rounded px-2 py-1 text-xs text-red-700 hover:bg-red-50">Damage</button>
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
