import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createSupplier, deleteSupplier, listSuppliers, updateSupplier } from '../../api/suppliers'
import type { Supplier, SupplierCreate } from '../../api/suppliers'
import { extractApiError } from '../../api/client'

const EMPTY: SupplierCreate = {
  supplier_code: '', supplier_name: '', contact_person: '',
  email: '', phone: '', gst_number: '', drug_license_number: '', address: '',
}

const FIELDS: { key: keyof SupplierCreate; label: string; span?: boolean; placeholder?: string }[] = [
  { key: 'supplier_code',       label: 'Supplier Code *' },
  { key: 'supplier_name',       label: 'Supplier Name *' },
  { key: 'contact_person',      label: 'Contact Person' },
  { key: 'email',               label: 'Email' },
  { key: 'phone',               label: 'Phone' },
  { key: 'gst_number',          label: 'GST Number', placeholder: 'e.g. 29AABCU9603R1ZX' },
  { key: 'drug_license_number', label: 'Drug License No.', placeholder: 'e.g. KA/DL/2024/001' },
  { key: 'address',             label: 'Address', span: true },
]

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
    onError: (e) => setError(extractApiError(e, 'Failed to save supplier.')),
  })

  const remove = useMutation({
    mutationFn: deleteSupplier,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['suppliers'] }),
    onError: (e) => setError(extractApiError(e, 'Cannot delete — supplier may be in use.')),
  })

  function openEdit(s: Supplier) {
    setEditing(s); setAdding(false)
    setForm({
      supplier_code: s.supplier_code,
      supplier_name: s.supplier_name,
      contact_person: s.contact_person ?? '',
      email: s.email ?? '',
      phone: s.phone ?? '',
      gst_number: s.gst_number ?? '',
      drug_license_number: s.drug_license_number ?? '',
      address: s.address ?? '',
    })
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
            {FIELDS.map(({ key, label, span, placeholder }) => (
              <div key={key} className={span ? 'sm:col-span-2' : ''}>
                <label className="mb-1 block text-xs font-medium text-slate-700">{label}</label>
                <input
                  value={form[key] ?? ''}
                  onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
                  placeholder={placeholder}
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
            <button onClick={cancel}
              className="rounded-lg border border-slate-300 px-5 py-2 text-sm text-slate-700 hover:bg-slate-50">Cancel</button>
          </div>
        </div>
      )}

      {isLoading ? <p className="text-sm text-slate-500">Loading…</p> : suppliers.length === 0 ? (
        <p className="text-sm text-slate-500">No suppliers yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Code</th>
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Contact</th>
                <th className="px-4 py-3 text-left">Phone / Email</th>
                <th className="px-4 py-3 text-left">GST</th>
                <th className="px-4 py-3 text-left">Drug Lic.</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {suppliers.map(s => (
                <tr key={s.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{s.supplier_code}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{s.supplier_name}</td>
                  <td className="px-4 py-3 text-slate-500">{s.contact_person ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-500">
                    <div>{s.phone ?? ''}</div>
                    <div className="text-xs text-slate-400">{s.email ?? ''}</div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{s.gst_number ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{s.drug_license_number ?? '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                      s.status === 'active' ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
                    }`}>{s.status}</span>
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex justify-center gap-3">
                      <button onClick={() => openEdit(s)} className="text-xs text-indigo-600 hover:underline">Edit</button>
                      <button onClick={() => { if (confirm(`Delete ${s.supplier_name}?`)) remove.mutate(s.id) }}
                        className="text-xs text-red-600 hover:underline">Delete</button>
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
