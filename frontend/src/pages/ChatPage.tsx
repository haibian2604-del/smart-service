import { useEffect, useState } from 'react'
import type { Actor, Widget } from '../types'
import { MessageList } from '../components/MessageList'
import { useChatStream } from '../hooks/useChatStream'
import { usePolling } from '../hooks/usePolling'
import { loadSelectedMerchant, saveSelectedMerchant, MERCHANTS } from '../lib/actor'
import { request } from '../lib/api'
import { SwitchIdentityButton } from '../components/SwitchIdentityButton'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { Logo } from '../components/Logo'

const QUICK_PROMPTS = ['你们有蓝牙耳机吗', '我的订单 #A1002 到哪了', '订单 #A1002 我要退款']


// 与后端 ensure_conversation 的 GREETING 保持一致（本地即时展示用，落库版在历史里）
const GREETING = "您好，我是智能购物助手 🛍️\n\n可以帮您查询商品、订单物流，或办理退款。有什么可以帮您？"

export function ChatPage({ actor }: { actor: Actor }) {
  const [input, setInput] = useState('')
  const [convs, setConvs] = useState<{ id: number; title: string }[]>([])
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [merchantId, setMerchantId] = useState<number>(loadSelectedMerchant() ?? MERCHANTS[0].id)
  const [pendingDelete, setPendingDelete] = useState<number | null>(null)
  const { messages, send, streaming, streamingText, pendingTaskId, conversationId, appendMessage, loadConversation } = useChatStream(null)

  const refreshConvs = () =>
    request<{ id: number; title: string }[]>(`/api/conversations?merchant_id=${merchantId}`).then(setConvs).catch(() => {})
  useEffect(() => { loadConversation(0, []); refreshConvs() }, [merchantId])

  const openConversation = async (id: number) => {
    type ConvMsg = { id: number; role: string; content: string; widgets: { kind: string; data: unknown }[] }
    const conv = await request<{ messages: ConvMsg[] }>(`/api/conversations/${id}`)
    loadConversation(id, conv.messages.map(m => ({
      id: String(m.id), role: m.role as 'user' | 'assistant', content: m.content,
      widgets: m.widgets as Widget[], toolCalls: [],
    })))
  }

  const removeConversation = async (id: number) => {
    await request(`/api/conversations/${id}`, { method: 'DELETE' })
    if (conversationId.current === id) loadConversation(0, [])
    setPendingDelete(null)
    refreshConvs()
  }

  return (
    <div className="flex h-screen bg-slate-50">
      {/* 历史会话侧边栏 */}
      {sidebarOpen ? (
        <aside className="flex w-60 flex-col border-r border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 px-3 py-3">
            <span className="flex items-center gap-2 text-sm font-medium text-slate-900"><Logo /> 智能客服</span>
            <button aria-label="收起历史会话" title="收起"
                    onClick={() => setSidebarOpen(false)}
                    className="rounded-lg px-2 py-1 text-xs text-slate-500 hover:bg-slate-100">« 收起</button>
          </div>
          <div role="tablist" aria-label="选择商家" className="mx-3 mt-3 grid grid-cols-2 gap-1 rounded-xl bg-slate-100 p-1">
            {MERCHANTS.map(m => (
              <button key={m.id} role="tab" aria-selected={merchantId === m.id}
                      onClick={() => { saveSelectedMerchant(m.id); setMerchantId(m.id) }}
                      className={`rounded-lg px-2 py-1.5 text-xs transition-colors duration-200 ${merchantId === m.id ? 'bg-white font-medium text-sky-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
                {m.name}
              </button>
            ))}
          </div>
          <button onClick={() => loadConversation(0, [])}
                  className="mx-3 mt-3 rounded-xl border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:border-sky-400 hover:text-sky-700">
            ＋ 新对话
          </button>
          <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="历史会话列表">
            {convs.map(c => (
              <div key={c.id} className={`group flex items-center rounded-lg ${conversationId.current === c.id ? 'bg-sky-50' : 'hover:bg-slate-50'}`}>
                <button onClick={() => void openConversation(c.id)}
                        className="flex-1 truncate px-3 py-2 text-left text-sm text-slate-700" title={c.title}>
                  {c.title}
                </button>
                <button aria-label={`删除会话 ${c.title}`} title="删除"
                        onClick={() => setPendingDelete(c.id)}
                        className="mr-1 hidden px-2 py-1 text-xs text-red-400 hover:text-red-600 group-hover:block">✕</button>
              </div>
            ))}
            {convs.length === 0 && <p className="px-3 py-2 text-xs text-slate-400">暂无历史会话</p>}
          </nav>
        </aside>
      ) : (
        <button aria-label="展开历史会话" title="展开历史会话"
                onClick={() => setSidebarOpen(true)}
                className="flex w-10 shrink-0 flex-col items-center gap-2 border-r border-slate-200 bg-white py-3 text-slate-500 hover:bg-slate-100">
          <Logo size={22} />
          <span>☰</span>
        </button>
      )}

      {/* 删除确认弹窗 */}
      <ConfirmDialog open={pendingDelete !== null} title="删除会话"
                     message="将删除该会话及其全部聊天记录，此操作不可恢复。"
                     onConfirm={() => { if (pendingDelete !== null) void removeConversation(pendingDelete) }}
                     onCancel={() => setPendingDelete(null)} />

      {/* 主聊天区 */}
      <div className="flex min-w-0 flex-1 flex-col">
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-900">{actor.name}</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">消费者</span>
        </div>
        <SwitchIdentityButton />
      </header>

      {pendingTaskId !== null && (
        <HandoffBanner conversationId={conversationId.current} taskId={pendingTaskId}
                       onFinal={appendMessage} />
      )}

      <MessageList messages={messages.length === 0
        ? [{ id: 'greeting', role: 'assistant' as const, content: GREETING, widgets: [], toolCalls: [] }]
        : messages} streamingText={streamingText} />

      {/* 快捷演示 */}
      <div className="flex gap-2 px-4 pb-2">
        {QUICK_PROMPTS.map(q => (
          <button key={q} onClick={() => send(q, merchantId)} disabled={streaming}
                  className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 transition-colors duration-200 hover:border-sky-500 hover:text-sky-700 disabled:opacity-50">
            {q}
          </button>
        ))}
      </div>

      {/* 输入区 */}
      <form className="flex gap-2 border-t border-slate-200 bg-white p-3"
            onSubmit={e => { e.preventDefault(); if (input.trim() && !streaming) { send(input.trim(), merchantId); setInput('') } }}>
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
    </div>
  )
}

/** 转人工横幅：轮询 status，商家处理后拉取最终回复追加到聊天。 */
export function HandoffBanner({ conversationId, taskId, onFinal }: {
  conversationId: number | null
  taskId: number
  onFinal: (msg: { content: string; widgets: Widget[] }) => void
}) {
  type ConvMsg = { role: string; content: string; widgets: Widget[] }
  usePolling(async () => {
    if (!conversationId) return false
    const s = await request<{ pending_human: boolean; task_id: number | null }>(
      `/api/conversations/${conversationId}/status`)
    if (!s.pending_human) {
      const conv = await request<{ messages: ConvMsg[] }>(
        `/api/conversations/${conversationId}`)
      const last = [...conv.messages].reverse().find(m => m.role === 'assistant')
      if (last) onFinal({ content: last.content, widgets: last.widgets })
      return true
    }
    return false
  }, 2000, true)

  return (
    <div role="status" className="flex items-center gap-2 border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-amber-800">
      <span className="h-2 w-2 animate-pulse rounded-full bg-amber-500" aria-hidden />
      已转人工，等待商家审核（工单 #{taskId}）
    </div>
  )
}
