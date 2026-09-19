import { Logo } from '../components/Logo'
import { MERCHANTS, saveSelectedMerchant } from '../lib/actor'

/** 用户进入对话前选择要咨询的商家。 */
export function MerchantPickPage() {
  const pick = (id: number) => {
    saveSelectedMerchant(id)
    window.location.assign('/chat')
  }
  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-3 p-6">
      <h1 className="mb-2 flex items-center justify-center gap-2 text-xl font-semibold"><Logo /> 选择要咨询的商家</h1>
      {MERCHANTS.map(m => (
        <button key={m.id} onClick={() => pick(m.id)}
                className="rounded-xl border border-slate-200 px-4 py-3 text-left hover:border-sky-400 hover:bg-sky-50">
          <div className="font-medium">{m.name}</div>
          <div className="text-sm text-slate-500">进入与 {m.name} 的对话</div>
        </button>
      ))}
    </div>
  )
}
