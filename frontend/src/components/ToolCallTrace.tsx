import type { Message } from '../types'

export function ToolCallTrace({ toolCalls }: { toolCalls: Message['toolCalls'] }) {
  if (!toolCalls.length) return null
  return (
    <details className="mb-1.5 rounded-lg border border-amber-200 bg-amber-50 px-2.5 py-1.5 text-xs text-amber-800">
      <summary className="cursor-pointer select-none font-medium">工具调用 × {toolCalls.length}</summary>
      <ul className="mt-1.5 space-y-1">
        {toolCalls.map((t, i) => (
          <li key={i} className="font-mono">
            <span className="rounded bg-amber-100 px-1 py-0.5">{t.name}</span>
            <span className="ml-1.5 break-all text-amber-700">{JSON.stringify(t.args)}</span>
          </li>
        ))}
      </ul>
    </details>
  )
}
