import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createWarehouse, listWarehouses, updateWarehouse } from '../../api/warehouses'
import type { Warehouse, WarehouseCreate } from '../../api/warehouses'

const EMPTY: WarehouseCreate = { warehouse_code: '', warehouse_name: '', address: '', contact_details: '' }

export function WarehouseList() {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<Warehouse | null>(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<WarehouseCreate>(EMPTY)
  const [error, setError] = useState<string | null>(null)

  const { data: warehouses = [], isLoading } = useQuery({ queryKey: ['warehouses'], queryFn: listWarehouses })

  const save = useMutation({
    mutationFn: async () => editing ? updateWarehouse(editing.id, form) : createWarehouse(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['warehouses'] }); cancel() },
    onError: () => setError('Failed to save warehouse.'),
  })

  function openEdit(w: Warehouse) {
    setEditing(w); setAdding(false)
    setForm({
      warehouse_code: w.warehouse_code,
      warehouse_name: w.warehouse_name,
      address: w.address ?? '',
      contact_details: w.contact_details ?? '',
    })
    setError(null)
  }

  function cancel() { setAdding(false); setEditing(null); setForm(EMPTY); setError(null) }

  const showForm = adding || editing !== null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Warehouses</h2>
        {!showForm && (
          <button onClick={() => { setAdding(true); setEditing(null); setForm(EMPTY) }}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
            + Add Warehouse
          </button>
        )}
      </div>

      {showForm && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <h3 className="mb-4 text-sm font-semibold text-indigo-900">{editing ? 'Edit Warehouse' : 'New Warehouse'}</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {([
              ['warehouse_code', 'Code *'],
              ['warehouse_name', 'Name *'],
              ['address', 'Address'],
              ['contact_details', 'Contact Details'],
            ] as [keyof WarehouseCreate, string][]).map(([field, label]) => (
              <div key={field}>
                <label className="mb-1 block text-xs font-medium text-slate-700">{label}</label>
                <input
                  value={form[field] as string ?? ''}
                  onChange={e => setForm(p => ({ ...p, [field]: e.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
            ))}
          </div>
          {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
          <div className="mt-4 flex gap-3">
            <button onClick={() => save.mutate()} disabled={save.isPending}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50">
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
            <button onClick={cancel} className="rounded-lg border border-slate-300 px-5 py-2 text-sm text-slate-700 hover:bg-slate-50">Cancel</button>
          </div>
        </div>
      )}

      {isLoading ? <p className="text-sm text-slate-500">Loading…</p> : warehouses.length === 0 ? (
        <p className="text-sm text-slate-500">No warehouses yet.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Code</th>
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Address</th>
                <th className="px-4 py-3 text-left">Contact</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {warehouses.map(w => (
                <tr key={w.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-slate-600">{w.warehouse_code}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{w.warehouse_name}</td>
                  <td className="px-4 py-3 text-slate-500">{w.address ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-500">{w.contact_details ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${w.is_active ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
                      {w.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => openEdit(w)} className="text-xs text-indigo-600 hover:underline">Edit</button>
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
