import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { ChatPage, HandoffBanner } from './ChatPage'

const actor = { id: 1, role: 'user' as const, name: '演示用户', merchantId: null }

vi.mock('../hooks/useChatStream', () => ({
  useChatStream: () => ({
    messages: [{ id: '1', role: 'user', content: '有耳机吗', widgets: [], toolCalls: [] }],
    send: vi.fn(), streaming: false, streamingText: '', pendingTaskId: null,
    conversationId: { current: null },
  }),
}))
vi.mock('../hooks/usePolling', () => ({ usePolling: vi.fn() }))
vi.mock('../lib/api', () => ({ request: vi.fn().mockResolvedValue({ pending_human: false, task_id: null }) }))

describe('ChatPage', () => {
  it('renders identity bar and existing messages', () => {
    render(<MemoryRouter><ChatPage actor={actor} /></MemoryRouter>)
    expect(screen.getByText('演示用户')).toBeInTheDocument()
    expect(screen.getByText('有耳机吗')).toBeInTheDocument()
  })

  it('shows handoff banner when a human task is pending', () => {
    render(<HandoffBanner conversationId={3} taskId={7} onResolved={vi.fn()} />)
    expect(screen.getByText(/已转人工，等待商家审核/)).toBeInTheDocument()
  })

  it('renders quick demo prompts', () => {
    render(<MemoryRouter><ChatPage actor={actor} /></MemoryRouter>)
    expect(screen.getByRole('button', { name: /有蓝牙耳机吗/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /订单.*到哪了/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /退款/ })).toBeInTheDocument()
  })
})
