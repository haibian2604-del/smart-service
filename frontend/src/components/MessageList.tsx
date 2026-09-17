import { useEffect, useRef } from 'react'
import type { Message } from '../types'
import { MessageBubble } from './MessageBubble'

export function MessageList({ messages, streamingText }: {
  messages: Message[]
  streamingText: string
}) {
  const endRef = useRef<HTMLDivElement>(null)
  useEffect(() => { endRef.current?.scrollIntoView?.({ behavior: 'smooth' }) }, [messages.length, streamingText])

  return (
    <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
      {messages.map(m => (
        <MessageBubble key={m.id} role={m.role} content={m.content}
                       widgets={m.widgets} toolCalls={m.toolCalls} />
      ))}
      {streamingText && (
        <MessageBubble role="assistant" content={streamingText} widgets={[]} toolCalls={[]} streaming />
      )}
      <div ref={endRef} />
    </div>
  )
}
