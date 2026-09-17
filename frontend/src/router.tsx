import { Navigate, Route, Routes } from 'react-router-dom'
import { ChatPage } from './pages/ChatPage'
import { MerchantPage } from './pages/MerchantPage'
import { RolePickPage } from './pages/RolePickPage'
import type { Actor } from './types'

export function AppRoutes({ actor }: { actor: Actor | null }) {
  if (actor === null) {
    return (
      <Routes>
        <Route path="*" element={<RolePickPage />} />
      </Routes>
    )
  }
  return (
    <Routes>
      <Route path="/" element={<Navigate to={actor.role === 'user' ? '/chat' : '/merchant'} replace />} />
      <Route path="/chat" element={actor.role === 'user' ? <ChatPage actor={actor} /> : <Denied />} />
      <Route path="/merchant" element={actor.role === 'merchant' ? <MerchantPage actor={actor} /> : <Denied />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

function Denied() {
  return <div className="flex h-screen items-center justify-center text-slate-500">无权访问该页面</div>
}
