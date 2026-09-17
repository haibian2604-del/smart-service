import type { Actor } from '../types'

export function ChatPage({ actor }: { actor: Actor }) {
  return <div className="p-6">对话工作台（{actor.name}，Task 29 实现）</div>
}
