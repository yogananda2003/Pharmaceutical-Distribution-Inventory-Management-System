import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { searchMedicines, listMedicines } from '../../api/medicines'
import type { Medicine } from '../../api/medicines'

interface CartItem {
  medicine: Medicine
  quantity: number
  unitPrice: string
}

export function ProductSearch() {
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [cart, setCart] = useState<CartItem[]>([])

  const { data: searchResults, isLoading } = useQuery({
    queryKey: ['medicines', 'search', query],
    queryFn: () => (query.length >= 2 ? searchMedicines(query) : listMedicines()),
    staleTime: 30_000,
  })

  function addToCart(medicine: Medicine) {
    setCart((prev) => {
      const existing = prev.find((c) => c.medicine.id === medicine.id)
      if (existing) {
        return prev.map((c) =>
          c.medicine.id === medicine.id ? { ...c, quantity: c.quantity + 1 } : c,
        )
      }
      return [...prev, { medicine, quantity: 1, unitPrice: '0.00' }]
    })
  }

  function updateQty(medicineId: string, qty: number) {
    if (qty <= 0) {
      setCart((prev) => prev.filter((c) => c.medicine.id !== medicineId))
    } else {
      setCart((prev) =>
        prev.map((c) => (c.medicine.id === medicineId ? { ...c, quantity: qty } : c)),
      )
    }
  }

  function updatePrice(medicineId: string, price: string) {
    setCart((prev) =>
      prev.map((c) => (c.medicine.id === medicineId ? { ...c, unitPrice: price } : c)),
    )
  }

  function proceedToOrder() {
    navigate('/customer/order/new', { state: { cart } })
  }

  const medicines = searchResults ?? []

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <input
          type="search"
          placeholder="Search medicines by name or code…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
          aria-label="Search medicines"
        />
      </div>

      {isLoading && <p className="text-slate-500 text-sm">Searching…</p>}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {medicines.map((med) => (
          <div key={med.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="font-semibold text-slate-900">{med.name}</p>
            <p className="text-xs text-slate-500">
              {med.code} · {med.dosage_form} · {med.strength}
            </p>
            <p className="mt-1 text-xs text-slate-400">{med.unit_type}</p>
            <button
              onClick={() => addToCart(med)}
              className="mt-3 w-full rounded-lg bg-indigo-600 py-1.5 text-xs font-semibold text-white hover:bg-indigo-700"
            >
              Add to cart
            </button>
          </div>
        ))}
        {!isLoading && medicines.length === 0 && (
          <p className="col-span-3 text-sm text-slate-400">No medicines found.</p>
        )}
      </div>

      {cart.length > 0 && (
        <div className="rounded-xl border border-indigo-200 bg-indigo-50 p-4">
          <h2 className="mb-3 font-semibold text-indigo-900">Cart ({cart.length} items)</h2>
          <ul className="space-y-2">
            {cart.map((item) => (
              <li key={item.medicine.id} className="flex items-center gap-2 text-sm">
                <span className="flex-1 text-slate-700">{item.medicine.name}</span>
                <input
                  type="number"
                  min={1}
                  value={item.quantity}
                  onChange={(e) => updateQty(item.medicine.id, Number(e.target.value))}
                  className="w-16 rounded border border-slate-300 px-2 py-0.5 text-center text-xs"
                  aria-label={`Quantity for ${item.medicine.name}`}
                />
                <input
                  type="text"
                  value={item.unitPrice}
                  onChange={(e) => updatePrice(item.medicine.id, e.target.value)}
                  placeholder="Price"
                  className="w-20 rounded border border-slate-300 px-2 py-0.5 text-xs"
                  aria-label={`Unit price for ${item.medicine.name}`}
                />
                <button
                  onClick={() => updateQty(item.medicine.id, 0)}
                  className="text-red-500 hover:text-red-700 text-xs"
                >
                  ✕
                </button>
              </li>
            ))}
          </ul>
          <button
            onClick={proceedToOrder}
            className="mt-4 w-full rounded-lg bg-indigo-600 py-2 text-sm font-semibold text-white hover:bg-indigo-700"
          >
            Place Order →
          </button>
        </div>
      )}
    </div>
  )
}
