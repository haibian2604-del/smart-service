import { useCallback, useRef, useState } from 'react'
import type { ChatEvent, Message, Widget } from '../types'
import { parseSSEChunk } from '../lib/sse'

let seq = 0
const nextId = () => `m${++seq}`

export function useChatStream(conversationId: number | null) {
  const [messages, setMessages] = useState<Message[]>([])
  const [streamingText, setStreamingText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [pendingTaskId, setPendingTaskId] = useState<number | null>(null)
  const convRef = useRef(conversationId)
  convRef.current = conversationId

  const send = useCallback(async (text: string) => {
    const actor = JSON.parse(localStorage.getItem('smart-service.actor') ?? 'null')
    setMessages(m => [...m, { id: nextId(), role: 'user', content: text, widgets: [], toolCalls: [] }])
    setStreaming(true)
    setStreamingText('')
    setPendingTaskId(null)

    const widgets: Widget[] = []
    let reply = ''

    try {
      const resp = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Actor-Id': String(actor?.id ?? '') },
        body: JSON.stringify({ conversation_id: convRef.current, message: text }),
      })
      if (!resp.ok || !resp.body) throw new Error(`stream failed: ${resp.status}`)

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      for (;;) {
        const { done, value } = await reader.read()
        if (done) break
        const { events, buffer: rest } = parseSSEChunk(decoder.decode(value, { stream: true }), buffer)
        buffer = rest
        for (const e of events as ChatEvent[]) {
          if (e.type === 'token') { reply += e.text; setStreamingText(reply) }
          else if (e.type === 'widget') widgets.push({ kind: e.kind, data: e.data })
          else if (e.type === 'meta') convRef.current = e.conversation_id
          else if (e.type === 'awaiting_human') setPendingTaskId(e.task_id)
          else if (e.type === 'error') reply += `\n[出错] ${e.message}`
        }
      }
    } catch (err) {
      reply = `连接失败：${String(err)}`
    } finally {
      setMessages(m => [...m, { id: nextId(), role: 'assistant', content: reply, widgets, toolCalls: [] }])
      setStreaming(false)
      setStreamingText('')
    }
  }, [])

  return { messages, send, streaming, streamingText, pendingTaskId, conversationId: convRef }
}
