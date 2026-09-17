export type Role = 'user' | 'merchant'

export interface Actor {
  id: number
  role: Role
  name: string
  merchantId: number | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  widgets: Widget[]
  toolCalls: { name: string; args: Record<string, unknown> }[]
}

export interface Widget {
  kind: 'order' | 'refund' | 'product_list'
  data: Record<string, unknown>
}

export type ChatEvent =
  | { type: 'meta'; conversation_id: number }
  | { type: 'token'; text: string }
  | { type: 'tool_call'; name: string; args: Record<string, unknown> }
  | { type: 'widget'; kind: Widget['kind']; data: Record<string, unknown> }
  | { type: 'awaiting_human'; task_id: number }
  | { type: 'done'; conversation_id: number }
  | { type: 'error'; message: string }
