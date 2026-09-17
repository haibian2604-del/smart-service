import { DEMO_ACTORS, saveActor, type Actor } from '../lib/actor'

export function RolePickPage() {
  const pick = (a: Actor) => {
    saveActor(a)
    // 整页跳转：身份切换无需保留的状态，reload 保证路由守卫读到最新身份
    window.location.assign(a.role === 'user' ? '/chat' : '/merchant')
  }
  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-3 p-6">
      <h1 className="mb-2 text-center text-xl font-semibold">选择身份</h1>
      {DEMO_ACTORS.map(a => (
        <button key={a.id} onClick={() => pick(a)}
                className="rounded-xl border border-slate-200 px-4 py-3 text-left hover:border-blue-400 hover:bg-blue-50">
          <div className="font-medium">{a.name}</div>
          <div className="text-sm text-slate-500">{a.role === 'user' ? '消费者 · 进入对话' : `商家 · 租户 #${a.merchantId}`}</div>
        </button>
      ))}
    </div>
  )
}
