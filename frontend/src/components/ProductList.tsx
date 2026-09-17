import type { Product } from '../types'

export function ProductList({ data }: { data: Product[] }) {
  return (
    <div className="grid w-full grid-cols-2 gap-2">
      {data.map(p => (
        <div key={p.id} className="rounded-xl border border-slate-200 bg-white p-3 text-left">
          <div className="text-sm font-medium text-slate-900">{p.name}</div>
          {p.category && <div className="mt-0.5 text-xs text-slate-500">{p.category}</div>}
          <div className="mt-1.5 flex items-baseline justify-between">
            <span className="font-medium text-slate-900">¥{p.price}</span>
            <span className="text-xs text-slate-400">库存 {p.stock}</span>
          </div>
        </div>
      ))}
    </div>
  )
}
