import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { adjustStock, damageStock, listBatches, stockIn } from '../../api/inventory'
import type { InventoryBatch } from '../../api/inventory'

type Action = 'stock-in' | 'adjust' | 'damage'

interface ActionState {
  batch: InventoryBatch
  type: Action
  value: string   // quantity (stock-in / damage) OR quantity_delta (adjust, can be negative)
  reference: string
}

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  exhausted: 'bg-slate-100 text-slate-500',
  expired: 'bg-red-100 text-red-700',
}

const ACTION_META: Record<Action, { label: string; hint: string; color: string }> = {
  'stock-in': { label: 'Add Stock',            hint: 'Quantity to add (must be > 0)',              color: 'emerald' },
  'adjust':   { label: 'Adjust Quantity',       hint: 'Delta: positive to increase, negative to decrease', color: 'amber' },
  'damage':   { label: 'Write Off Damaged',     hint: 'Quantity to write off (must be > 0)',        color: 'red' },
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
      const num = parseInt(action.value)
      if (isNaN(num)) throw new Error('Enter a valid number')
      if (action.type === 'stock-in') {
        if (num <= 0) throw new Error('Quantity must be greater than 0')
        return stockIn(action.batch.id, num, action.reference || undefined)
      }
      if (action.type === 'adjust') {
        if (num === 0) throw new Error('Delta cannot be zero')
        // adjustStock sends { quantity_delta: num, reference_number }
        return adjustStock(action.batch.id, num, action.reference || undefined)
      }
      // damage
      if (num <= 0) throw new Error('Quantity must be greater than 0')
      return damageStock(action.batch.id, num, action.reference || undefined)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['inventory-batches'] })
      setAction(null)
      setError(null)
    },
    onError: (e: Error) => setError(e.message || 'Action failed. Check the values.'),
  })

  function openAction(batch: InventoryBatch, type: Action) {
    setAction({ batch, type, value: '', reference: '' })
    setError(null)
  }

  return (
    <div className="space-y-4">
      <h2 className="text-lg font-semibold text-slate-900">Stock / Inventory Batches</h2>

      {action && (
        <div className={`rounded-xl border p-5 ${
          action.type === 'stock-in' ? 'border-emerald-200 bg-emerald-50' :
          action.type === 'adjust'   ? 'border-amber-200 bg-amber-50' :
                                       'border-red-200 bg-red-50'
        }`}>
          <h3 className="mb-1 text-sm font-semibold text-slate-800">{ACTION_META[action.type].label}</h3>
          <p className="mb-3 text-xs text-slate-600">
            Batch: <strong>{action.batch.batch_number}</strong>
            {' — '}{action.batch.medicine_name ?? action.batch.medicine_id}
            {'  |  '}Available: <strong>{action.batch.quantity_available}</strong>
            {'  Reserved: '}<strong>{action.batch.quantity_reserved}</strong>
          </p>
          <div className="flex flex-wrap gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">
                {action.type === 'adjust' ? 'Delta (e.g. −10 or +50) *' : 'Quantity *'}
              </label>
              <input
                type="number"
                value={action.value}
                onChange={e => setAction(a => a ? { ...a, value: e.target.value } : a)}
                placeholder={ACTION_META[action.type].hint}
                className="w-32 rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none"
              />
            </div>
            <div className="flex-1 min-w-[200px]">
              <label className="mb-1 block text-xs font-medium text-slate-700">
                Reference / Reason (optional)
              </label>
              <input
                value={action.reference}
                onChange={e => setAction(a => a ? { ...a, reference: e.target.value } : a)}
                placeholder={action.type === 'damage' ? 'e.g. Expired batch' : action.type === 'adjust' ? 'e.g. Physical count 2026-06-16' : 'e.g. GRN-001'}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none"
              />
            </div>
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => mutate.mutate()}
              disabled={mutate.isPending}
              className={`rounded-lg px-5 py-2 text-sm font-semibold text-white disabled:opacity-50 ${
                action.type === 'stock-in' ? 'bg-emerald-600 hover:bg-emerald-700' :
                action.type === 'adjust'   ? 'bg-amber-600 hover:bg-amber-700' :
                                             'bg-red-600 hover:bg-red-700'
              }`}
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
        <p className="text-sm text-slate-500">No batches found. Receive goods from a Purchase Order to add stock.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
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
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[b.status] ?? 'bg-slate-100 text-slate-500'}`}>
                      {b.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex justify-center gap-2">
                      <button onClick={() => openAction(b, 'stock-in')}
                        className="rounded px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50">+Stock</button>
                      <button onClick={() => openAction(b, 'adjust')}
                        className="rounded px-2 py-1 text-xs text-amber-700 hover:bg-amber-50">Adjust</button>
                      <button onClick={() => openAction(b, 'damage')}
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
