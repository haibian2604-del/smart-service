import { useNavigate } from 'react-router-dom'
import { clearActor } from '../lib/actor'

export function SwitchIdentityButton() {
  const nav = useNavigate()
  return (
    <button onClick={() => { clearActor(); nav('/') }}
            className="rounded-lg px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100">
      切换身份
    </button>
  )
}
