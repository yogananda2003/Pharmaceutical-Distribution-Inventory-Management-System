const STATUS_STYLES: Record<string, string> = {
  draft: 'bg-slate-100 text-slate-700',
  placed: 'bg-blue-100 text-blue-700',
  approved: 'bg-indigo-100 text-indigo-700',
  allocated: 'bg-violet-100 text-violet-700',
  picked: 'bg-purple-100 text-purple-700',
  packed: 'bg-fuchsia-100 text-fuchsia-700',
  dispatched: 'bg-amber-100 text-amber-700',
  delivered: 'bg-lime-100 text-lime-700',
  completed: 'bg-emerald-100 text-emerald-700',
  cancelled: 'bg-red-100 text-red-700',
}

export function OrderStatusBadge({ status }: { status: string }) {
  const cls = STATUS_STYLES[status] ?? 'bg-slate-100 text-slate-700'
  return (
    <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  )
}
