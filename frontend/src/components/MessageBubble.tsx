import type { Message, Widget } from '../types'
import { ToolCallTrace } from './ToolCallTrace'
import { OrderCard } from './OrderCard'
import { RefundCard } from './RefundCard'
import { ProductList } from './ProductList'

function WidgetView({ w }: { w: Widget }) {
  if (w.kind === 'order') return <OrderCard data={w.data as never} />
  if (w.kind === 'refund') return <RefundCard data={w.data as never} />
  return <ProductList data={w.data as never} />
}

interface Props {
  role: Message['role']
  content: string
  widgets: Widget[]
  toolCalls: Message['toolCalls']
  streaming?: boolean
}

export function MessageBubble({ role, content, widgets, toolCalls, streaming }: Props) {
  const isUser = role === 'user'
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed transition-colors duration-200 ${
        isUser ? 'bg-slate-900 text-white' : 'border border-slate-200 bg-white text-slate-900'
      }`}>
        {!isUser && <ToolCallTrace toolCalls={toolCalls} />}
        {content}
        {streaming && !content && (
          <span className="inline-block h-4 w-2 animate-pulse rounded-sm bg-slate-400" aria-label="正在输入" />
        )}
        {streaming && content && (
          <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse rounded-sm bg-slate-400" />
        )}
        {widgets.map((w, i) => <div key={i} className="mt-2"><WidgetView w={w} /></div>)}
      </div>
    </div>
  )
}
