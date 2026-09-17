import { useCallback, useRef, useState } from 'react'
import type { ChatEvent, Message, Widget } from '../types'
import { parseSSEChunk } from '../lib/sse'


export function useChatStream(conversationId: number | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [streamingText, setStreamingText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [pendingTaskId, setPendingTaskId] = useState<number | null>(null)
  const convRef = useRef<number | null>(conversationId)

  const send = useCallback(async (text: string) => {
    const actor = JSON.parse(localStorage.getItem('smart-service.actor') ?? 'null')
    setMessages(m => [...m, { id: crypto.randomUUID(), role: 'user', content: text, widgets: [], toolCalls: [] }])
    setStreaming(true)
    setStreamingText('')
    setPendingTaskId(null)

    const widgets: Widget[] = []
    let reply = ''
    let buffer = ''
    const handle = (chunk: string) => {
      const { events, buffer: rest } = parseSSEChunk(chunk, buffer)
      buffer = rest
      for (const e of events as ChatEvent[]) {
        if (e.type === 'token') { reply += e.text; setStreamingText(reply) }
        else if (e.type === 'widget') widgets.push({ kind: e.kind, data: e.data } as Widget)  // 网络边界唯一 cast
        else if (e.type === 'meta') convRef.current = e.conversation_id
        else if (e.type === 'awaiting_human') setPendingTaskId(e.task_id)
        else if (e.type === 'error') reply += `\n[出错] ${e.message}`
      }
    }

    try {
      // ponytail: 真实 Chromium 下页面内 POST 流式 fetch 读不到数据（裸 fetch / 伪造响应均正常，原因未明），
      // 改用 XHR onprogress 渐进读取，对 SSE/代理兼容性最好；若日后查明可换回 fetch
      await new Promise<void>((resolve, reject) => {
        const xhr = new XMLHttpRequest()
        xhr.open('POST', '/api/chat/stream')
        xhr.setRequestHeader('Content-Type', 'application/json')
        xhr.setRequestHeader('X-Actor-Id', String(actor?.id ?? ''))
        let seen = 0
        xhr.onprogress = () => { handle(xhr.responseText.slice(seen)); seen = xhr.responseText.length }
        xhr.onload = () => { handle(xhr.responseText.slice(seen)); if (xhr.status !== 200) reject(new Error(`HTTP ${xhr.status}`)); else resolve() }
        xhr.onerror = () => reject(new Error('网络错误'))
        xhr.send(JSON.stringify({ conversation_id: convRef.current, message: text }))
      })
    } catch (err) {
      reply = `连接失败：${String(err)}`
    } finally {
      setMessages(m => [...m, { id: crypto.randomUUID(), role: 'assistant', content: reply, widgets, toolCalls: [] }])
      setStreaming(false)
      setStreamingText('')
    }
  }, [])

  const appendMessage = useCallback((msg: { content: string; widgets?: Widget[] }) => {
    setMessages(m => [...m, { id: crypto.randomUUID(), role: 'assistant', content: msg.content, widgets: msg.widgets ?? [], toolCalls: [] }])
    setPendingTaskId(null)
  }, [])

  return { messages, send, streaming, streamingText, pendingTaskId, conversationId: convRef, appendMessage }
}
