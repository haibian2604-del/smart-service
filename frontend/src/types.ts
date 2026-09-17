export type Role = 'user' | 'merchant'

export interface Actor {
  id: number
  role: Role
  name: string
  merchantId: number | null
}

export interface OrderItem { name: string; quantity: number; unit_price: string }

export interface OrderData {
  order_no: string
  status: string
  total_amount: string
  created_at: string
  shipped_at?: string | null
  items: OrderItem[]
}

export interface RefundData {
  refund_no?: string
  amount: string
  status?: string
  trigger?: string | null
}

export interface Product {
  id: number
  name: string
  category: string | null
  price: string
  stock: number
}

export interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  widgets: Widget[]
  toolCalls: { name: string; args: Record<string, unknown> }[]
}

export type Widget =
  | { kind: 'order'; data: OrderData }
  | { kind: 'refund'; data: RefundData }
  | { kind: 'product_list'; data: Product[] }

export type ChatEvent =
  | { type: 'meta'; conversation_id: number }
  | { type: 'token'; text: string }
  | { type: 'tool_call'; name: string; args: Record<string, unknown> }
  | { type: 'widget'; kind: Widget['kind']; data: Widget['data'] }
  | { type: 'awaiting_human'; task_id: number }
  | { type: 'done'; conversation_id: number }
  | { type: 'error'; message: string }

export const TRIGGER_LABEL: Record<string, string> = {
  amount_over_threshold: '金额超限',
  already_shipped: '已发货/签收',
  user_requested: '用户要求人工',
}
