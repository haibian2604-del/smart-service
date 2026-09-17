import { clearActor } from '../lib/actor'

export function SwitchIdentityButton() {
  return (
    <button onClick={() => { clearActor(); window.location.assign('/') }}
            className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
      切换身份
    </button>
  )
}
