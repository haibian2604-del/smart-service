import { Navigate, Route, Routes } from 'react-router-dom'
import { ChatPage } from './pages/ChatPage'
import { MerchantPage } from './pages/MerchantPage'
import { MerchantPickPage } from './pages/MerchantPickPage'
import { RolePickPage } from './pages/RolePickPage'
import { loadActor, loadSelectedMerchant } from './lib/actor'
import type { Actor } from './types'

export function AppRoutes() {
  // 在 Router 内部读取：导航触发重渲染时自然拿到最新身份
  const actor: Actor | null = loadActor()
  const merchantId = actor?.role === 'user' ? loadSelectedMerchant() : null
  if (actor === null) {
    return (
      <Routes>
        <Route path="*" element={<RolePickPage />} />
      </Routes>
    )
  }
  if (actor.role === 'user' && merchantId === null) {
    return (
      <Routes>
        <Route path="*" element={<MerchantPickPage />} />
      </Routes>
    )
  }
  return (
    <Routes>
      <Route path="/" element={<Navigate to={actor.role === 'user' ? '/pick-merchant' : '/merchant'} replace />} />
      <Route path="/pick-merchant" element={actor.role === 'user' ? <MerchantPickPage /> : <Denied />} />
      <Route path="/chat" element={actor.role === 'user' ? <ChatPage actor={actor} /> : <Denied />} />
      <Route path="/merchant" element={actor.role === 'merchant' ? <MerchantPage actor={actor} /> : <Denied />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function Denied() {
  return <div className="flex h-screen items-center justify-center text-slate-500">无权访问该页面</div>
}
