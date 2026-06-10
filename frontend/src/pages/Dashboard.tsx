import { useHealth } from '../api/health'

export function Dashboard() {
  const { data, isLoading, isError } = useHealth()

  return (
    <main className="mx-auto max-w-3xl p-8">
      <h1 className="text-2xl font-semibold text-slate-900">
        Pharma Distribution & Inventory Management
      </h1>
      <p className="mt-2 text-slate-600">
        API status:{' '}
        {isLoading && <span className="text-slate-400">checking…</span>}
        {isError && <span className="text-red-600">unreachable</span>}
        {data?.success && <span className="text-emerald-600">{data.data.status}</span>}
      </p>
    </main>
  )
}
