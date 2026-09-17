import { StatusBadge } from './StatusBadge'
import type { OrderData } from '../types'

export function OrderCard({ data }: { data: OrderData }) {
  return (
    <div className="w-full rounded-xl border border-slate-200 bg-white p-3 text-left text-sm">
      <div className="flex items-center justify-between">
        <span className="font-mono font-medium text-slate-900">{data.order_no}</span>
        <StatusBadge status={data.status} />
      </div>
      <ul className="mt-2 space-y-0.5 text-xs text-slate-600">
        {data.items.map((it, i) => (
          <li key={i} className="flex justify-between">
            <span>{it.name} × {it.quantity}</span>
            <span className="font-mono">¥{it.unit_price}</span>
          </li>
        ))}
      </ul>
      <div className="mt-2 flex items-center justify-between border-t border-slate-100 pt-2">
        <span className="text-xs text-slate-500">{data.created_at?.slice(0, 10)}</span>
        <span className="font-medium text-slate-900">¥{data.total_amount}</span>
      </div>
    </div>
  )
}
