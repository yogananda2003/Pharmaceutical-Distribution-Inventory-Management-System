import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { searchMedicines, listMedicines, DOSAGE_FORMS } from '../../api/medicines'
import type { Medicine } from '../../api/medicines'

interface CartItem {
  medicine: Medicine
  quantity: number
  unitPrice: string
}

const DOSAGE_LABELS: Record<string, string> = {
  tablet: 'Tablet', capsule: 'Capsule', injection: 'Injection',
  syrup: 'Syrup', ointment: 'Ointment', drops: 'Drops',
  powder: 'Powder', cream: 'Cream', gel: 'Gel', inhaler: 'Inhaler',
}

export function ProductSearch() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [dosageFilter, setDosageFilter] = useState('')
  const [cart, setCart] = useState<CartItem[]>([])

  const { data: results = [], isLoading } = useQuery({
    queryKey: ['medicines', 'search', query],
    queryFn: () => (query.length >= 2 ? searchMedicines(query) : listMedicines()),
    staleTime: 30_000,
  })

  // Apply dosage form filter client-side
  const medicines = dosageFilter
    ? results.filter(m => m.dosage_form === dosageFilter)
    : results

  function addToCart(medicine: Medicine) {
    setCart(prev => {
      const existing = prev.find(c => c.medicine.id === medicine.id)
      if (existing) return prev.map(c => c.medicine.id === medicine.id ? { ...c, quantity: c.quantity + 1 } : c)
      return [...prev, { medicine, quantity: 1, unitPrice: '' }]
    })
  }

  function updateQty(medicineId: string, qty: number) {
    if (qty <= 0) setCart(prev => prev.filter(c => c.medicine.id !== medicineId))
    else setCart(prev => prev.map(c => c.medicine.id === medicineId ? { ...c, quantity: qty } : c))
  }

  function updatePrice(medicineId: string, price: string) {
    setCart(prev => prev.map(c => c.medicine.id === medicineId ? { ...c, unitPrice: price } : c))
  }

  const cartInCart = (id: string) => cart.find(c => c.medicine.id === id)

  const total = cart.reduce((sum, c) => sum + c.quantity * (parseFloat(c.unitPrice) || 0), 0)

  return (
    <div className="space-y-5">
      <h2 className="text-lg font-semibold text-slate-900">Browse Products</h2>

      {/* Search & Filter bar */}
      <div className="flex flex-wrap gap-3">
        <input
          type="search"
          placeholder="Search medicines by name or code…"
          value={query}
          onChange={e => setQuery(e.target.value)}
          className="flex-1 min-w-[200px] rounded-lg border border-slate-300 px-4 py-2 text-sm focus:border-indigo-500 focus:outline-none"
          aria-label="Search medicines"
        />
        <select
          value={dosageFilter}
          onChange={e => setDosageFilter(e.target.value)}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"
        >
          <option value="">All Forms</option>
          {DOSAGE_FORMS.map(df => <option key={df} value={df}>{DOSAGE_LABELS[df]}</option>)}
        </select>
        {(query || dosageFilter) && (
          <button onClick={() => { setQuery(''); setDosageFilter('') }}
            className="rounded-lg border border-slate-300 px-3 py-2 text-sm text-slate-500 hover:text-red-600">
            ✕ Clear
          </button>
        )}
      </div>

      <div className="flex gap-6">
        {/* Product grid */}
        <div className="flex-1">
          {isLoading ? (
            <p className="text-sm text-slate-500">Searching…</p>
          ) : medicines.length === 0 ? (
            <p className="text-sm text-slate-400">No medicines found{query ? ` for "${query}"` : ''}.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {medicines.map(med => {
                const inCart = cartInCart(med.id)
                return (
                  <div key={med.id} className={`rounded-xl border bg-white p-4 shadow-sm transition-colors ${inCart ? 'border-indigo-300' : 'border-slate-200'}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-semibold text-slate-900 truncate">{med.name}</p>
                        <p className="text-xs text-slate-500">{med.generic_name}</p>
                      </div>
                      <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500 capitalize">
                        {med.dosage_form}
                      </span>
                    </div>
                    <p className="mt-1.5 text-xs text-slate-400">
                      {med.code} · {med.strength} · {med.unit_type}
                    </p>
                    {inCart ? (
                      <div className="mt-3 flex items-center gap-2">
                        <button onClick={() => updateQty(med.id, inCart.quantity - 1)}
                          className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-300 text-slate-600 hover:bg-slate-50">−</button>
                        <span className="w-8 text-center text-sm font-medium">{inCart.quantity}</span>
                        <button onClick={() => updateQty(med.id, inCart.quantity + 1)}
                          className="flex h-7 w-7 items-center justify-center rounded-full border border-slate-300 text-slate-600 hover:bg-slate-50">+</button>
                        <span className="ml-auto text-xs font-medium text-indigo-600">In cart</span>
                      </div>
                    ) : (
                      <button onClick={() => addToCart(med)}
                        className="mt-3 w-full rounded-lg bg-indigo-600 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700">
                        Add to cart
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Cart panel — sticky on the side */}
        {cart.length > 0 && (
          <div className="w-72 shrink-0">
            <div className="sticky top-4 rounded-xl border border-indigo-200 bg-indigo-50 p-4 space-y-3">
              <h3 className="font-semibold text-indigo-900">Cart ({cart.length} items)</h3>
              <ul className="space-y-3 max-h-80 overflow-y-auto">
                {cart.map(item => (
                  <li key={item.medicine.id} className="rounded-lg bg-white p-2.5 text-sm space-y-1.5">
                    <div className="flex items-center justify-between gap-1">
                      <span className="font-medium text-slate-800 truncate text-xs">{item.medicine.name}</span>
                      <button onClick={() => updateQty(item.medicine.id, 0)}
                        className="shrink-0 text-slate-400 hover:text-red-500">✕</button>
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => updateQty(item.medicine.id, item.quantity - 1)}
                        className="flex h-6 w-6 items-center justify-center rounded border border-slate-300 text-xs">−</button>
                      <input
                        type="number" min={1} value={item.quantity}
                        onChange={e => updateQty(item.medicine.id, Number(e.target.value))}
                        className="w-12 rounded border border-slate-300 px-1 py-0.5 text-center text-xs"
                        aria-label={`Qty for ${item.medicine.name}`}
                      />
                      <button onClick={() => updateQty(item.medicine.id, item.quantity + 1)}
                        className="flex h-6 w-6 items-center justify-center rounded border border-slate-300 text-xs">+</button>
                      <span className="text-slate-400 text-xs">×</span>
                      <input
                        type="number" min={0} step="0.01" value={item.unitPrice}
                        onChange={e => updatePrice(item.medicine.id, e.target.value)}
                        placeholder="Price ₹"
                        className="w-20 rounded border border-slate-300 px-1 py-0.5 text-xs"
                        aria-label={`Price for ${item.medicine.name}`}
                      />
                    </div>
                  </li>
                ))}
              </ul>
              <div className="border-t border-indigo-200 pt-2">
                <div className="flex justify-between text-sm font-semibold text-indigo-900">
                  <span>Total</span>
                  <span>₹{total.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                </div>
              </div>
              <button
                onClick={() => navigate('/customer/order/new', { state: { cart } })}
                className="w-full rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700">
                Proceed to Order →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
