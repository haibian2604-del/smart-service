import { useState } from 'react'
import { Logo } from '../components/Logo'
import { MERCHANTS, saveSelectedMerchant } from '../lib/actor'

/** 头像配色：按 id 取色，两个商家视觉可区分。 */
const AVATAR_STYLES = ['bg-sky-100 text-sky-700', 'bg-emerald-100 text-emerald-700']

/** 用户进入对话前选择要咨询的商家。 */
export function MerchantPickPage() {
  const [picking, setPicking] = useState<number | null>(null)

  const pick = (id: number) => {
    if (picking !== null) return
    setPicking(id)
    saveSelectedMerchant(id)
    window.location.assign('/chat')
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-md flex-col justify-center p-6">
      <header className="mb-8 flex flex-col items-center gap-3 text-center">
        <Logo size={44} />
        <div>
          <h1 className="text-2xl font-semibold text-slate-900">选择要咨询的商家</h1>
          <p className="mt-1 text-sm text-slate-500">进入后会自动连接对应商家的智能客服</p>
        </div>
      </header>

      <div className="flex flex-col gap-3">
        {MERCHANTS.map((m, i) => {
          const isPicking = picking === m.id
          return (
            <button key={m.id} onClick={() => pick(m.id)} disabled={picking !== null}
                    className="group flex cursor-pointer items-center gap-4 rounded-2xl border border-slate-200 bg-white p-4 text-left
                               shadow-sm transition-all duration-200
                               hover:-translate-y-0.5 hover:border-sky-400 hover:shadow-md
                               focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-sky-500
                               active:translate-y-0 active:scale-[0.99] disabled:cursor-wait disabled:opacity-60">
              <span aria-hidden
                    className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl text-lg font-semibold ${AVATAR_STYLES[i % AVATAR_STYLES.length]}`}>
                {m.name.slice(0, 1)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block font-medium text-slate-900">{m.name}</span>
                <span className="mt-0.5 block text-sm text-slate-500">
                  {isPicking ? '正在进入…' : '进入与该商家的对话'}
                </span>
              </span>
              <span aria-hidden
                    className="text-slate-300 transition-all duration-200 group-hover:translate-x-0.5 group-hover:text-sky-500">
                →
              </span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
