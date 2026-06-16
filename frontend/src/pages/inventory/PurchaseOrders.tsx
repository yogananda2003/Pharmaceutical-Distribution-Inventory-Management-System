import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  createPurchaseOrder, getPurchaseOrder, listPurchaseOrders, receiveGoods, updatePOStatus,
} from '../../api/purchases'
import type { POCreate, POItemCreate, ReceiveItem, PurchaseOrder } from '../../api/purchases'
import { listMedicines } from '../../api/medicines'
import { listSuppliers } from '../../api/suppliers'
import { listWarehouses } from '../../api/warehouses'

type View = 'list' | 'create' | 'receive'

const PO_STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  confirmed: 'bg-blue-100 text-blue-700',
  partially_received: 'bg-amber-100 text-amber-700',
  received: 'bg-emerald-100 text-emerald-700',
  cancelled: 'bg-red-100 text-red-700',
}

// Display label for each receive item — keyed by purchase_order_item_id
interface ReceiveItemMeta {
  label: string     // "Medicine Name (qty pending)"
  pending: number
}

export function PurchaseOrders() {
  const qc = useQueryClient()
  const [view, setView] = useState<View>('list')
  const [selectedPO, setSelectedPO] = useState<PurchaseOrder | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Create PO state
  const [poForm, setPoForm] = useState<Omit<POCreate, 'items'>>({
    supplier_id: '', order_date: new Date().toISOString().slice(0, 10), expected_delivery_date: '', notes: '',
  })
  const [poItems, setPoItems] = useState<POItemCreate[]>([{ medicine_id: '', quantity_ordered: 1, unit_price: '' }])

  // Receive goods state — uses corrected ReceiveItem interface
  const [receiveItems, setReceiveItems] = useState<ReceiveItem[]>([])
  const [receiveMeta, setReceiveMeta] = useState<Record<string, ReceiveItemMeta>>({})

  const { data: pos = [], isLoading } = useQuery({ queryKey: ['purchase-orders'], queryFn: () => listPurchaseOrders() })
  const { data: medicines = [] } = useQuery({ queryKey: ['medicines'], queryFn: listMedicines })
  const { data: suppliers = [] } = useQuery({ queryKey: ['suppliers'], queryFn: listSuppliers })
  const { data: warehouses = [] } = useQuery({ queryKey: ['warehouses'], queryFn: listWarehouses })

  const createPO = useMutation({
    mutationFn: () => createPurchaseOrder({ ...poForm, items: poItems.filter(i => i.medicine_id) }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['purchase-orders'] }); setView('list'); setError(null) },
    onError: () => setError('Failed to create Purchase Order.'),
  })

  const updateStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => updatePOStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['purchase-orders'] }),
    onError: () => setError('Status update failed.'),
  })

  const receive = useMutation({
    // Backend GoodsReceiptRequest: { items, reference_number?, remarks? } — NO received_date
    mutationFn: () => receiveGoods(selectedPO!.id, { items: receiveItems }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['purchase-orders'] })
      qc.invalidateQueries({ queryKey: ['inventory-batches'] })
      setView('list'); setSelectedPO(null); setError(null)
    },
    onError: () => setError('Failed to receive goods. Ensure all required fields are filled.'),
  })

  async function openReceive(po: PurchaseOrder) {
    const full = await getPurchaseOrder(po.id)
    setSelectedPO(full)

    const meta: Record<string, ReceiveItemMeta> = {}
    const items: ReceiveItem[] = full.items.map(i => {
      const med = medicines.find(m => m.id === i.medicine_id)
      const pending = Math.max(0, i.quantity_ordered - i.quantity_received)
      meta[i.id] = { label: `${med?.name ?? i.medicine_id}`, pending }
      return {
        // Matches backend GoodsReceiptItemRequest exactly
        purchase_order_item_id: i.id,   // NOT medicine_id
        quantity: pending,              // NOT quantity_received
        batch_number: '',
        expiry_date: '',
        warehouse_id: '',
      }
    }).filter(i => i.quantity > 0)     // skip fully-received items

    setReceiveItems(items)
    setReceiveMeta(meta)
    setView('receive')
    setError(null)
  }

  function updateReceiveItem(idx: number, field: keyof ReceiveItem, value: string | number) {
    setReceiveItems(items => items.map((it, i) => i === idx ? { ...it, [field]: value } : it))
  }

  if (view === 'create') {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <button onClick={() => setView('list')} className="text-sm text-indigo-600 hover:underline">← Back</button>
          <h2 className="text-lg font-semibold text-slate-900">New Purchase Order</h2>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
          <div className="grid gap-3 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Supplier *</label>
              <select value={poForm.supplier_id} onChange={e => setPoForm(p => ({ ...p, supplier_id: e.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500">
                <option value="">Select supplier…</option>
                {suppliers.map(s => <option key={s.id} value={s.id}>{s.supplier_name}</option>)}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Order Date *</label>
              <input type="date" value={poForm.order_date} onChange={e => setPoForm(p => ({ ...p, order_date: e.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500" />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Expected Delivery</label>
              <input type="date" value={poForm.expected_delivery_date} onChange={e => setPoForm(p => ({ ...p, expected_delivery_date: e.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:border-indigo-500" />
            </div>
          </div>

          <div>
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-sm font-medium text-slate-700">Items</h3>
              <button onClick={() => setPoItems(p => [...p, { medicine_id: '', quantity_ordered: 1, unit_price: '' }])}
                className="text-xs text-indigo-600 hover:underline">+ Add item</button>
            </div>
            <div className="space-y-2">
              {poItems.map((item, idx) => (
                <div key={idx} className="flex gap-2 items-end">
                  <div className="flex-1">
                    <label className="mb-1 block text-xs text-slate-500">Medicine</label>
                    <select value={item.medicine_id} onChange={e => setPoItems(p => p.map((it, i) => i === idx ? { ...it, medicine_id: e.target.value } : it))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none">
                      <option value="">Select…</option>
                      {medicines.map(m => <option key={m.id} value={m.id}>{m.name} ({m.code})</option>)}
                    </select>
                  </div>
                  <div className="w-24">
                    <label className="mb-1 block text-xs text-slate-500">Qty</label>
                    <input type="number" min={1} value={item.quantity_ordered}
                      onChange={e => setPoItems(p => p.map((it, i) => i === idx ? { ...it, quantity_ordered: Number(e.target.value) } : it))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none" />
                  </div>
                  <div className="w-28">
                    <label className="mb-1 block text-xs text-slate-500">Unit Price ₹</label>
                    <input value={item.unit_price}
                      onChange={e => setPoItems(p => p.map((it, i) => i === idx ? { ...it, unit_price: e.target.value } : it))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none" />
                  </div>
                  {poItems.length > 1 && (
                    <button onClick={() => setPoItems(p => p.filter((_, i) => i !== idx))}
                      className="pb-2 text-red-500 hover:text-red-700 text-sm">✕</button>
                  )}
                </div>
              ))}
            </div>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className="flex gap-3">
            <button onClick={() => createPO.mutate()} disabled={createPO.isPending}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
              {createPO.isPending ? 'Creating…' : 'Create PO'}
            </button>
            <button onClick={() => setView('list')} className="rounded-lg border border-slate-300 px-5 py-2 text-sm text-slate-700 hover:bg-slate-50">Cancel</button>
          </div>
        </div>
      </div>
    )
  }

  if (view === 'receive' && selectedPO) {
    return (
      <div className="space-y-5">
        <div className="flex items-center gap-3">
          <button onClick={() => setView('list')} className="text-sm text-indigo-600 hover:underline">← Back</button>
          <h2 className="text-lg font-semibold text-slate-900">Receive Goods — {selectedPO.po_number}</h2>
        </div>

        {receiveItems.length === 0 ? (
          <p className="text-sm text-slate-500 rounded-xl border border-slate-200 bg-white p-5">
            All items on this PO have already been fully received.
          </p>
        ) : (
          <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4">
            <div className="space-y-4">
              {receiveItems.map((item, idx) => {
                const meta = receiveMeta[item.purchase_order_item_id]
                return (
                  <div key={idx} className="rounded-lg border border-slate-100 bg-slate-50 p-4">
                    <p className="mb-3 text-sm font-medium text-slate-800">
                      {meta?.label ?? item.purchase_order_item_id}
                      <span className="ml-2 text-xs text-slate-400">(pending: {meta?.pending ?? item.quantity})</span>
                    </p>
                    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                      <div>
                        <label className="mb-1 block text-xs text-slate-500">Qty to Receive *</label>
                        <input type="number" min={0} value={item.quantity}
                          onChange={e => updateReceiveItem(idx, 'quantity', Number(e.target.value))}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-slate-500">Batch Number *</label>
                        <input value={item.batch_number} onChange={e => updateReceiveItem(idx, 'batch_number', e.target.value)}
                          placeholder="e.g. BATCH-2026-001"
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-slate-500">Expiry Date *</label>
                        <input type="date" value={item.expiry_date} onChange={e => updateReceiveItem(idx, 'expiry_date', e.target.value)}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none" />
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-slate-500">Warehouse *</label>
                        <select value={item.warehouse_id} onChange={e => updateReceiveItem(idx, 'warehouse_id', e.target.value)}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none">
                          <option value="">Select…</option>
                          {warehouses.map(w => <option key={w.id} value={w.id}>{w.warehouse_name}</option>)}
                        </select>
                      </div>
                      <div>
                        <label className="mb-1 block text-xs text-slate-500">Mfg Date (optional)</label>
                        <input type="date" value={item.manufacturing_date ?? ''}
                          onChange={e => updateReceiveItem(idx, 'manufacturing_date', e.target.value)}
                          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none" />
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>

            {error && <p className="text-sm text-red-600">{error}</p>}
            <div className="flex gap-3">
              <button onClick={() => receive.mutate()} disabled={receive.isPending}
                className="rounded-lg bg-emerald-600 px-5 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-50">
                {receive.isPending ? 'Receiving…' : 'Confirm Receipt — Add to Stock'}
              </button>
              <button onClick={() => setView('list')} className="rounded-lg border border-slate-300 px-5 py-2 text-sm text-slate-700 hover:bg-slate-50">Cancel</button>
            </div>
          </div>
        )}
      </div>
    )
  }

  // List view
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Purchase Orders</h2>
        <button onClick={() => setView('create')}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
          + New PO
        </button>
      </div>

      {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}

      {isLoading ? <p className="text-sm text-slate-500">Loading…</p> : pos.length === 0 ? (
        <p className="text-sm text-slate-500">No purchase orders yet.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">PO #</th>
                <th className="px-4 py-3 text-left">Supplier</th>
                <th className="px-4 py-3 text-left">Date</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {pos.map(po => (
                <tr key={po.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono font-medium text-slate-900">{po.po_number}</td>
                  <td className="px-4 py-3 text-slate-600">{po.supplier_name ?? po.supplier_id}</td>
                  <td className="px-4 py-3 text-slate-600">{po.order_date}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${PO_STATUS_STYLES[po.status] ?? 'bg-slate-100 text-slate-600'}`}>
                      {po.status.replace('_', ' ')}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex justify-center gap-2">
                      {po.status === 'draft' && (
                        <button onClick={() => updateStatus.mutate({ id: po.id, status: 'confirmed' })}
                          className="rounded px-2 py-1 text-xs text-blue-700 hover:bg-blue-50">Confirm</button>
                      )}
                      {['confirmed', 'partially_received'].includes(po.status) && (
                        <button onClick={() => openReceive(po)}
                          className="rounded px-2 py-1 text-xs text-emerald-700 hover:bg-emerald-50">Receive Goods</button>
                      )}
                      {po.status === 'draft' && (
                        <button onClick={() => updateStatus.mutate({ id: po.id, status: 'cancelled' })}
                          className="rounded px-2 py-1 text-xs text-red-700 hover:bg-red-50">Cancel</button>
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
