import type { Actor } from '../types'

export function MerchantPage({ actor }: { actor: Actor }) {
  return <div className="p-6">待审批工单（{actor.name}，Task 30 实现）</div>
}
