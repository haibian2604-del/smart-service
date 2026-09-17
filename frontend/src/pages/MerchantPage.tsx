import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type { Actor } from '../types'
import { ApiError, request } from '../lib/api'
import { clearActor } from '../lib/actor'

interface Task {
  id: number
  type: string
  status: string
  thread_id: string
  payload: { order_no?: string; refund_no?: string; amount?: string; reason?: string; trigger?: string | null }
  created_at: string
}

const TRIGGER_LABEL: Record<string, string> = {
  amount_over_threshold: '金额超限',
  already_shipped: '已发货/签收',
  user_requested: '用户要求人工',
}

export function MerchantPage({ actor }: { actor: Actor }) {
  const nav = useNavigate()
  const [tasks, setTasks] = useState<Task[]>([])
  const [toast, setToast] = useState<string | null>(null)
  const [rejecting, setRejecting] = useState<number | null>(null)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(async () => {
    setTasks(await request<Task[]>('/api/merchant/tasks?status=pending'))
  }, [])

  useEffect(() => { void load() }, [load])

  const showToast = (msg: string) => { setToast(msg); setTimeout(() => setToast(null), 2500) }

  const resolve = async (id: number, decision: 'approved' | 'rejected', note: string | null) => {
    setBusy(true)
    try {
      const r = await request<{ refund_state: string }>(`/api/merchant/tasks/${id}/resolve`, {
        method: 'POST',
        body: JSON.stringify({ decision, note }),
      })
      showToast(r.refund_state === 'refunded' ? '已批准，退款已受理' : '已驳回')
      await load()
    } catch (e) {
      showToast(e instanceof ApiError && e.status === 409 ? '该工单已被处理' : `操作失败：${String(e)}`)
    } finally {
      setBusy(false)
      setRejecting(null); setNote('')
    }
  }

  return (
    <div className="mx-auto min-h-screen max-w-3xl bg-slate-50 p-4">
      {/* 身份条：让租户隔离可被看见 */}
      <header className="mb-4 flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-900">{actor.name}</span>
          <span className="rounded-full bg-sky-100 px-2 py-0.5 text-xs text-sky-800">商家 · 租户 #{actor.merchantId}</span>
        </div>
        <button onClick={() => { clearActor(); nav('/') }}
                className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
          切换身份
        </button>
      </header>

      <h1 className="mb-3 text-lg font-semibold text-slate-900">待审批工单</h1>

      {tasks.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-10 text-center text-sm text-slate-500">
          暂无待审批工单
        </div>
      ) : (
        <ul className="space-y-3">
          {tasks.map(t => (
            <li key={t.id} className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between">
                <span className="font-mono font-medium text-slate-900">{t.payload.order_no ?? t.payload.refund_no}</span>
                <span className="font-medium text-slate-900">¥{t.payload.amount}</span>
              </div>
              <div className="mt-1 text-sm text-slate-600">原因：{t.payload.reason ?? '（未填写）'}</div>
              <div className="mt-1 flex items-center justify-between text-xs">
                <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800">
                  {TRIGGER_LABEL[t.payload.trigger ?? ''] ?? t.payload.trigger}
                </span>
                <span className="text-slate-400">{t.created_at.slice(0, 16).replace('T', ' ')}</span>
              </div>

              {rejecting === t.id ? (
                <div className="mt-3 flex gap-2">
                  <input value={note} onChange={e => setNote(e.target.value)}
                         placeholder="驳回原因"
                         aria-label="驳回原因"
                         className="flex-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm outline-none focus:border-red-400" />
                  <button disabled={busy || !note.trim()} onClick={() => resolve(t.id, 'rejected', note.trim())}
                          className="rounded-lg bg-red-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-40">
                    确认驳回
                  </button>
                  <button onClick={() => { setRejecting(null); setNote('') }}
                          className="rounded-lg px-3 py-1.5 text-sm text-slate-500 hover:bg-slate-100">
                    取消
                  </button>
                </div>
              ) : (
                <div className="mt-3 flex justify-end gap-2">
                  <button disabled={busy} onClick={() => setRejecting(t.id)}
                          className="rounded-lg border border-red-200 px-4 py-1.5 text-sm font-medium text-red-600 transition-colors duration-200 hover:bg-red-50 disabled:opacity-40">
                    驳回
                  </button>
                  <button disabled={busy} onClick={() => resolve(t.id, 'approved', null)}
                          className="rounded-lg bg-emerald-600 px-4 py-1.5 text-sm font-medium text-white transition-colors duration-200 hover:bg-emerald-500 disabled:opacity-40">
                    批准
                  </button>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {toast && (
        <div role="alert" className="fixed bottom-6 left-1/2 -translate-x-1/2 rounded-full bg-slate-900 px-4 py-2 text-sm text-white shadow-lg">
          {toast}
        </div>
      )}
    </div>
  )
}
