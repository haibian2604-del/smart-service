const MAP: Record<string, { label: string; cls: string }> = {
  pending:   { label: '待审核', cls: 'bg-amber-100 text-amber-800' },
  approved:  { label: '已批准', cls: 'bg-emerald-100 text-emerald-800' },
  rejected:  { label: '已驳回', cls: 'bg-red-100 text-red-700' },
  refunded:  { label: '已退款', cls: 'bg-emerald-100 text-emerald-800' },
  draft:     { label: '草稿',   cls: 'bg-slate-100 text-slate-600' },
  // 订单状态：中性灰蓝
  unpaid:    { label: '待付款', cls: 'bg-slate-100 text-slate-700' },
  paid:      { label: '已付款', cls: 'bg-sky-100 text-sky-800' },
  shipped:   { label: '已发货', cls: 'bg-sky-100 text-sky-800' },
  delivered: { label: '已签收', cls: 'bg-slate-200 text-slate-800' },
  cancelled: { label: '已取消', cls: 'bg-slate-100 text-slate-500' },
}

export function StatusBadge({ status, label }: { status: string; label?: string }) {
  const meta = MAP[status] ?? { label: status, cls: 'bg-slate-100 text-slate-600' }
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${meta.cls}`}>
      {label ?? meta.label}
    </span>
  )
}
