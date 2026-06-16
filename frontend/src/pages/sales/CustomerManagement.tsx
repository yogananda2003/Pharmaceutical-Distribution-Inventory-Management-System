import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createCustomer, deleteCustomer, listCustomers, updateCustomer } from '../../api/customers'
import type { Customer, CustomerCreate } from '../../api/customers'
import { extractApiError } from '../../api/client'
import { useAuth } from '../../contexts/AuthContext'

const EMPTY: CustomerCreate = {
  customer_code: '', business_name: '', contact_person: '',
  email: '', phone: '', gst_number: '', drug_license_number: '',
  address: '', credit_limit: '0.00', status: 'active',
}

type Field = { key: keyof CustomerCreate; label: string; span?: boolean; type?: string; placeholder?: string }

const FIELDS: Field[] = [
  { key: 'customer_code',       label: 'Customer Code *',     placeholder: 'e.g. CUST-001' },
  { key: 'business_name',       label: 'Business Name *',     placeholder: 'e.g. Apollo Pharmacy' },
  { key: 'contact_person',      label: 'Contact Person' },
  { key: 'phone',               label: 'Phone' },
  { key: 'email',               label: 'Email',               type: 'email' },
  { key: 'gst_number',          label: 'GST Number',          placeholder: 'e.g. 29AABCU9603R1ZX' },
  { key: 'drug_license_number', label: 'Drug License No.',    placeholder: 'e.g. KA/DL/2024/001' },
  { key: 'credit_limit',        label: 'Credit Limit (₹)',    type: 'number', placeholder: '0.00' },
  { key: 'address',             label: 'Address',             span: true },
]

const STATUS_STYLES: Record<string, string> = {
  active: 'bg-emerald-100 text-emerald-700',
  inactive: 'bg-slate-100 text-slate-500',
  blacklisted: 'bg-red-100 text-red-700',
}

export function CustomerManagement() {
  const qc = useQueryClient()
  const { role } = useAuth()
  const canWrite = role === 'admin' || role === 'sales_representative'

  const [editing, setEditing] = useState<Customer | null>(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<CustomerCreate>(EMPTY)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')

  const { data: customers = [], isLoading } = useQuery({
    queryKey: ['customers'],
    queryFn: () => listCustomers(),
  })

  const save = useMutation({
    mutationFn: async () =>
      editing ? updateCustomer(editing.id, form) : createCustomer(form),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['customers'] }); cancel() },
    onError: (e) => setError(extractApiError(e, 'Failed to save customer.')),
  })

  const remove = useMutation({
    mutationFn: deleteCustomer,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['customers'] }),
    onError: (e) => setError(extractApiError(e, 'Cannot delete customer.')),
  })

  function openEdit(c: Customer) {
    setEditing(c); setAdding(false)
    setForm({
      customer_code: c.customer_code,
      business_name: c.business_name,
      contact_person: c.contact_person ?? '',
      email: c.email ?? '',
      phone: c.phone ?? '',
      gst_number: c.gst_number ?? '',
      drug_license_number: c.drug_license_number ?? '',
      address: c.address ?? '',
      credit_limit: c.credit_limit,
      status: c.status,
    })
    setError(null)
  }

  function cancel() { setAdding(false); setEditing(null); setForm(EMPTY); setError(null) }

  const showForm = adding || editing !== null

  const filtered = search
    ? customers.filter(c =>
        c.business_name.toLowerCase().includes(search.toLowerCase()) ||
        c.customer_code.toLowerCase().includes(search.toLowerCase()) ||
        (c.phone ?? '').includes(search))
    : customers

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Customers</h2>
        {canWrite && !showForm && (
          <button onClick={() => { setAdding(true); setEditing(null); setForm(EMPTY) }}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
            + Add Customer
          </button>
        )}
      </div>

      {/* Add / Edit form */}
      {showForm && canWrite && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <h3 className="mb-4 text-sm font-semibold text-indigo-900">{editing ? 'Edit Customer' : 'New Customer'}</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {FIELDS.map(({ key, label, span, type, placeholder }) => (
              <div key={key} className={span ? 'sm:col-span-2' : ''}>
                <label className="mb-1 block text-xs font-medium text-slate-700">{label}</label>
                <input
                  type={type ?? 'text'}
                  value={form[key] ?? ''}
                  onChange={e => setForm(p => ({ ...p, [key]: e.target.value }))}
                  placeholder={placeholder}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
            ))}
            <div>
              <label className="mb-1 block text-xs font-medium text-slate-700">Status</label>
              <select value={form.status ?? 'active'} onChange={e => setForm(p => ({ ...p, status: e.target.value }))}
                className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none">
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
                <option value="blacklisted">Blacklisted</option>
              </select>
            </div>
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

      {/* Search */}
      {!showForm && (
        <input
          type="search"
          placeholder="Search by name, code or phone…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full max-w-sm rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        />
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-slate-500">{search ? 'No customers match.' : 'No customers yet.'}</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Code</th>
                <th className="px-4 py-3 text-left">Business Name</th>
                <th className="px-4 py-3 text-left">Contact</th>
                <th className="px-4 py-3 text-left">Phone / Email</th>
                <th className="px-4 py-3 text-left">GST / Drug Lic.</th>
                <th className="px-4 py-3 text-right">Credit Limit</th>
                <th className="px-4 py-3 text-left">Status</th>
                {canWrite && <th className="px-4 py-3 text-center">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.map(c => (
                <tr key={c.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-xs text-slate-600">{c.customer_code}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">
                    {c.business_name}
                    {c.address && <div className="text-xs font-normal text-slate-400 truncate max-w-[200px]">{c.address}</div>}
                  </td>
                  <td className="px-4 py-3 text-slate-500">{c.contact_person ?? '—'}</td>
                  <td className="px-4 py-3 text-slate-500">
                    <div>{c.phone ?? ''}</div>
                    <div className="text-xs text-slate-400">{c.email ?? ''}</div>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-500">
                    <div>{c.gst_number ?? '—'}</div>
                    <div className="text-slate-400">{c.drug_license_number ?? ''}</div>
                  </td>
                  <td className="px-4 py-3 text-right font-medium text-slate-700">
                    ₹{Number(c.credit_limit).toLocaleString('en-IN', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[c.status] ?? 'bg-slate-100 text-slate-500'}`}>
                      {c.status}
                    </span>
                  </td>
                  {canWrite && (
                    <td className="px-4 py-3 text-center">
                      <div className="flex justify-center gap-3">
                        <button onClick={() => openEdit(c)} className="text-xs text-indigo-600 hover:underline">Edit</button>
                        <button onClick={() => { if (confirm(`Delete ${c.business_name}?`)) remove.mutate(c.id) }}
                          className="text-xs text-red-600 hover:underline">Delete</button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
