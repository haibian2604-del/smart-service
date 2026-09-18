import { useEffect, useState } from 'react'
import type { Actor, Widget } from '../types'
import { MessageList } from '../components/MessageList'
import { useChatStream } from '../hooks/useChatStream'
import { usePolling } from '../hooks/usePolling'
import { request } from '../lib/api'
import { SwitchIdentityButton } from '../components/SwitchIdentityButton'

const QUICK_PROMPTS = ['你们有蓝牙耳机吗', '我的订单 #A1002 到哪了', '订单 #A1002 我要退款']

export function ChatPage({ actor }: { actor: Actor }) {
  const [input, setInput] = useState('')
  const [convs, setConvs] = useState<{ id: number; title: string }[]>([])
  const { messages, send, streaming, streamingText, pendingTaskId, conversationId, appendMessage, loadConversation } = useChatStream(null)

  useEffect(() => {
    request<{ id: number; title: string }[]>('/api/conversations').then(setConvs).catch(() => {})
  }, [])

  const openConversation = async (id: number) => {
    type ConvMsg = { id: number; role: string; content: string; widgets: { kind: string; data: unknown }[] }
    const conv = await request<{ messages: ConvMsg[] }>(`/api/conversations/${id}`)
    loadConversation(id, conv.messages.map(m => ({
      id: String(m.id), role: m.role as 'user' | 'assistant', content: m.content,
      widgets: m.widgets as Widget[], toolCalls: [],
    })))
  }

  return (
    <div className="flex h-screen flex-col bg-slate-50">
      {/* 身份条 */}
      <header className="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-medium text-slate-900">{actor.name}</span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">消费者</span>
        </div>
        <div className="flex items-center gap-2">
          <select aria-label="历史会话"
                  className="max-w-40 rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-600"
                  value=""
                  onChange={e => { if (e.target.value) void openConversation(Number(e.target.value)) }}>
            <option value="">历史会话</option>
            {convs.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
          </select>
          <button onClick={() => loadConversation(0, [])}
                  className="rounded-lg px-2 py-1 text-xs text-slate-600 hover:bg-slate-100">新对话</button>
          {conversationId.current !== null && conversationId.current > 0 && (
            <button aria-label="删除当前会话" title="删除当前会话"
                    onClick={async () => {
                      if (!window.confirm('确定删除当前会话及其全部聊天记录？')) return
                      await request(`/api/conversations/${conversationId.current}`, { method: 'DELETE' })
                      loadConversation(0, [])
                      request<{ id: number; title: string }[]>('/api/conversations').then(setConvs).catch(() => {})
                    }}
                    className="rounded-lg px-2 py-1 text-xs text-red-500 hover:bg-red-50">删除</button>
          )}
        </div>
        <SwitchIdentityButton />
      </header>

      {pendingTaskId !== null && (
        <HandoffBanner conversationId={conversationId.current} taskId={pendingTaskId}
                       onFinal={appendMessage} />
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
