import { useState } from 'react'
import type { Actor } from '../types'
import { MessageList } from '../components/MessageList'
import { useChatStream } from '../hooks/useChatStream'
import { usePolling } from '../hooks/usePolling'
import { request } from '../lib/api'
import { SwitchIdentityButton } from '../components/SwitchIdentityButton'

const QUICK_PROMPTS = ['你们有蓝牙耳机吗', '我的订单 #A1002 到哪了', '订单 #A1002 我要退款']

export function ChatPage({ actor }: { actor: Actor }) {
  const [input, setInput] = useState('')
  const { messages, send, streaming, streamingText, pendingTaskId, conversationId } = useChatStream(null)

  return (
    <div className="flex h-screen flex-col bg-slate-50">
      {/* 身份条 */}
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-900">{actor.name}</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">消费者</span>
        </div>
        <SwitchIdentityButton />
      </header>

      {pendingTaskId !== null && (
        <HandoffBanner conversationId={conversationId.current} taskId={pendingTaskId}
                       onResolved={() => location.reload()} />
      )}

      <MessageList messages={messages} streamingText={streamingText} />

      {/* 快捷演示 */}
      <div className="flex gap-2 px-4 pb-2">
        {QUICK_PROMPTS.map(q => (
          <button key={q} onClick={() => send(q)} disabled={streaming}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 transition-colors duration-200 hover:border-sky-500 hover:text-sky-700 disabled:opacity-50">
            {q}
          </button>
        ))}
      </div>

      {/* 输入区 */}
      <form className="flex gap-2 border-t border-slate-200 bg-white p-3"
            onSubmit={e => { e.preventDefault(); if (input.trim() && !streaming) { send(input.trim()); setInput('') } }}>
        <textarea
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              if (input.trim() && !streaming) { send(input.trim()); setInput('') }
            }
          }}
          rows={1}
          aria-label="输入消息"
          placeholder="输入消息，Enter 发送，Shift+Enter 换行"
          className="flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-sky-500"
        />
        <button type="submit" disabled={streaming || !input.trim()}
                className="rounded-xl bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors duration-200 hover:bg-slate-700 disabled:opacity-40">
          发送
        </button>
      </form>
    </div>
  )
}

/** 转人工横幅：轮询 status，pending_human 转 false 后拉结果并刷新会话。 */
export function HandoffBanner({ conversationId, taskId, onResolved }: {
  conversationId: number | null
  taskId: number
  onResolved: () => void
}) {
  usePolling(async () => {
    if (!conversationId) return false
    const s = await request<{ pending_human: boolean; task_id: number | null }>(
      `/api/conversations/${conversationId}/status`)
    if (!s.pending_human) { onResolved(); return true }
    return false
  }, 2000, true)

  return (
    <div role="status" className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" aria-hidden />
      已转人工，等待商家审核（工单 #{taskId}）
    </div>
  )
}
