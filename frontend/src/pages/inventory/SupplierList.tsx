import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createSupplier, listSuppliers, updateSupplier } from '../../api/suppliers'
import type { Supplier, SupplierCreate } from '../../api/suppliers'

const EMPTY: SupplierCreate = { supplier_code: '', name: '', email: '', phone: '', address: '' }

export function SupplierList() {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<Supplier | null>(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<SupplierCreate>(EMPTY)
  const [error, setError] = useState<string | null>(null)

  const { data: suppliers = [], isLoading } = useQuery({ queryKey: ['suppliers'], queryFn: listSuppliers })

  const save = useMutation({
    mutationFn: async () => editing ? updateSupplier(editing.id, form) : createSupplier(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['suppliers'] }); cancel() },
    onError: () => setError('Failed to save supplier.'),
  })

  function openEdit(s: Supplier) {
    setEditing(s); setAdding(false)
    setForm({ supplier_code: s.supplier_code, name: s.name, email: s.email ?? '', phone: s.phone ?? '', address: s.address ?? '' })
    setError(null)
  }

  function cancel() { setAdding(false); setEditing(null); setForm(EMPTY); setError(null) }

  const showForm = adding || editing !== null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Suppliers</h2>
        {!showForm && (
          <button onClick={() => { setAdding(true); setEditing(null); setForm(EMPTY) }}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
            + Add Supplier
          </button>
        )}
      </div>

      {showForm && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <h3 className="mb-4 text-sm font-semibold text-indigo-900">{editing ? 'Edit Supplier' : 'New Supplier'}</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {([ ['supplier_code','Code *'], ['name','Name *'], ['email','Email'], ['phone','Phone'], ['address','Address'] ] as [keyof SupplierCreate, string][]).map(([f, label]) => (
              <div key={f} className={f === 'address' ? 'sm:col-span-2' : ''}>
                <label className="mb-1 block text-xs font-medium text-slate-700">{label}</label>
                <input value={form[f] ?? ''} onChange={e => setForm(p => ({ ...p, [f]: e.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none" />
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

      {isLoading ? <p className="text-sm text-slate-500">Loading…</p> : suppliers.length === 0 ? (
        <p className="text-sm text-slate-500">No suppliers yet.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Code</th>
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Email</th>
                <th className="px-4 py-3 text-left">Phone</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {suppliers.map(s => (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-slate-600">{s.supplier_code}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{s.name}</td>
                  <td className="px-4 py-3 text-slate-500">{s.email ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-500">{s.phone ?? '—'}</td>
                  <td className="px-4 py-3 text-center">
                    <button onClick={() => openEdit(s)} className="text-xs text-indigo-600 hover:underline">Edit</button>
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
