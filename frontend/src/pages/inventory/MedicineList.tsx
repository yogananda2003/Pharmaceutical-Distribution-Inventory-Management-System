import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { createMedicine, deleteMedicine, listMedicines, updateMedicine } from '../../api/medicines'
import type { Medicine, MedicineCreate } from '../../api/medicines'

const EMPTY: MedicineCreate = {
  code: '', name: '', generic_name: '', manufacturer: '',
  dosage_form: '', strength: '', unit_type: '',
}

export function MedicineList() {
  const qc = useQueryClient()
  const [editing, setEditing] = useState<Medicine | null>(null)
  const [adding, setAdding] = useState(false)
  const [form, setForm] = useState<MedicineCreate>(EMPTY)
  const [error, setError] = useState<string | null>(null)

  const { data: medicines = [], isLoading } = useQuery({
    queryKey: ['medicines'],
    queryFn: listMedicines,
  })

  const save = useMutation({
    mutationFn: async () => {
      if (editing) return updateMedicine(editing.id, form)
      return createMedicine(form)
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['medicines'] })
      setAdding(false)
      setEditing(null)
      setForm(EMPTY)
      setError(null)
    },
    onError: () => setError('Failed to save. Check all fields.'),
  })

  const remove = useMutation({
    mutationFn: deleteMedicine,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['medicines'] }),
    onError: () => setError('Cannot delete — medicine may be in use.'),
  })

  function openEdit(med: Medicine) {
    setEditing(med)
    setAdding(false)
    setForm({
      code: med.code, name: med.name, generic_name: med.generic_name,
      manufacturer: med.manufacturer, dosage_form: med.dosage_form,
      strength: med.strength, unit_type: med.unit_type,
    })
    setError(null)
  }

  function openAdd() {
    setEditing(null)
    setAdding(true)
    setForm(EMPTY)
    setError(null)
  }

  function cancel() { setAdding(false); setEditing(null); setForm(EMPTY); setError(null) }

  const showForm = adding || editing !== null

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-slate-900">Medicines</h2>
        {!showForm && (
          <button onClick={openAdd} className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
            + Add Medicine
          </button>
        )}
      </div>

      {showForm && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <h3 className="mb-4 text-sm font-semibold text-indigo-900">{editing ? 'Edit Medicine' : 'New Medicine'}</h3>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {([ ['code','Code *'], ['name','Name *'], ['generic_name','Generic Name *'],
                 ['manufacturer','Manufacturer *'], ['dosage_form','Dosage Form *'],
                 ['strength','Strength *'], ['unit_type','Unit Type *'] ] as [keyof MedicineCreate, string][]).map(([field, label]) => (
              <div key={field}>
                <label className="mb-1 block text-xs font-medium text-slate-700">{label}</label>
                <input
                  value={form[field] as string ?? ''}
                  onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
                />
              </div>
            ))}
          </div>
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => save.mutate()}
              disabled={save.isPending}
              className="rounded-lg bg-indigo-600 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {save.isPending ? 'Saving…' : 'Save'}
            </button>
            <button onClick={cancel} className="rounded-lg border border-slate-300 px-5 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
              Cancel
            </button>
          </div>
        </div>
      )}

      {isLoading ? (
        <p className="text-sm text-slate-500">Loading…</p>
      ) : medicines.length === 0 ? (
        <p className="text-sm text-slate-500">No medicines yet. Add one above.</p>
      ) : (
        <div className="overflow-hidden rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead className="bg-slate-50 text-xs uppercase text-slate-500">
              <tr>
                <th className="px-4 py-3 text-left">Code</th>
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-left">Generic</th>
                <th className="px-4 py-3 text-left">Form / Strength</th>
                <th className="px-4 py-3 text-left">Unit</th>
                <th className="px-4 py-3 text-center">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {medicines.map(med => (
                <tr key={med.id} className="hover:bg-slate-50">
                  <td className="px-4 py-3 font-mono text-slate-600">{med.code}</td>
                  <td className="px-4 py-3 font-medium text-slate-900">{med.name}</td>
                  <td className="px-4 py-3 text-slate-600">{med.generic_name}</td>
                  <td className="px-4 py-3 text-slate-600">{med.dosage_form} · {med.strength}</td>
                  <td className="px-4 py-3 text-slate-600">{med.unit_type}</td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex justify-center gap-3">
                      <button onClick={() => openEdit(med)} className="text-xs text-indigo-600 hover:underline">Edit</button>
                      <button
                        onClick={() => { if (confirm(`Delete ${med.name}?`)) remove.mutate(med.id) }}
                        className="text-xs text-red-600 hover:underline"
                      >Delete</button>
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
