import { StatusBadge } from './StatusBadge'

interface RefundData {
  refund_no?: string
  amount: string
  status?: string
  trigger?: string | null
}

const TRIGGER_LABEL: Record<string, string> = {
  amount_over_threshold: '金额超限',
  already_shipped: '已发货/签收',
  user_requested: '用户要求人工',
}

export function RefundCard({ data }: { data: RefundData }) {
  const stages = ['draft', 'pending', data.status === 'rejected' ? 'rejected' : 'approved', 'refunded']
  const activeIdx = stages.indexOf(data.status ?? 'draft')
  return (
    <div className="w-full rounded-xl border border-slate-200 bg-white p-3 text-sm">
      <div className="flex items-center justify-between">
        <span className="font-mono font-medium text-slate-900">{data.refund_no ?? '退款申请'}</span>
        <span className="font-medium text-slate-900">¥{data.amount}</span>
      </div>
      {data.trigger && (
        <div className="mt-1.5 text-xs text-amber-700">
          转人工原因：{TRIGGER_LABEL[data.trigger] ?? data.trigger}
        </div>
      )}
      <div className="mt-2.5 flex items-center gap-1">
        {stages.map((s, i) => (
          <div key={s} className="flex flex-1 items-center gap-1">
            <StatusBadge status={s} />
            {i < stages.length - 1 && (
              <span className={`h-px flex-1 ${i < activeIdx ? 'bg-emerald-400' : 'bg-slate-200'}`} />
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
