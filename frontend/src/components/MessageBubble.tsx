import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { Message } from '../types'
import { ToolCallTrace } from './ToolCallTrace'
import { OrderCard } from './OrderCard'
import { RefundCard } from './RefundCard'
import { ProductList } from './ProductList'

function WidgetView({ w }: { w: Message['widgets'][number] }) {
  if (w.kind === 'order') return <OrderCard data={w.data} />
  if (w.kind === 'refund') return <RefundCard data={w.data} />
  return <ProductList data={w.data} />
}

interface Props {
  role: Message['role']
  content: string
  widgets: Message['widgets']
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
        {isUser
          ? content
          : <div className="[&_p]:my-1 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_h1]:mt-2 [&_h2]:mt-2 [&_h3]:mt-2 [&_h1]:mb-1 [&_h2]:mb-1 [&_h3]:mb-1 [&_h1]:text-base [&_h2]:text-sm [&_h3]:text-sm [&_h1]:font-medium [&_h2]:font-medium [&_h3]:font-medium [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_pre]:overflow-x-auto [&_pre]:rounded-lg [&_pre]:bg-slate-100 [&_pre]:p-2 [&_a]:text-sky-600 [&_a]:underline [&_table]:w-full [&_table]:text-xs [&_th]:border [&_th]:px-1.5 [&_th]:py-0.5 [&_td]:border [&_td]:px-1.5 [&_td]:py-0.5">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
            </div>}
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
