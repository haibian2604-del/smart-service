import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MerchantPage } from './MerchantPage'
import { saveActor, DEMO_ACTORS } from '../lib/actor'

const actor = { id: 2, role: 'merchant' as const, name: '青柠数码', merchantId: 1 }

beforeEach(() => saveActor(actor))

const TASK = {
  id: 7, type: 'refund_review', status: 'pending', thread_id: '3',
  payload: { order_no: '#A1002', amount: '599.00', reason: '我要退款', trigger: 'already_shipped' },
  created_at: '2026-09-17T10:00:00Z',
}

describe('MerchantPage', () => {
  it('lists pending refund tasks of own tenant', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(
      new Response(JSON.stringify([TASK]), { status: 200 }))
    render(<MemoryRouter><MerchantPage actor={actor} /></MemoryRouter>)
    expect(await screen.findByText('#A1002')).toBeInTheDocument()
    expect(screen.getByText(/已发货/)).toBeInTheDocument()   // 触发原因中文映射
    expect(screen.getByText(/599\.00/)).toBeInTheDocument()
  })

  it('shows empty state when no pending task', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response('[]', { status: 200 }))
    render(<MemoryRouter><MerchantPage actor={actor} /></MemoryRouter>)
    expect(await screen.findByText(/暂无待审批/)).toBeInTheDocument()
  })

  it('posts resolve and refreshes list', async () => {
    const fetchMock = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify([TASK]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ refund_state: 'refunded' }), { status: 200 }))
      .mockResolvedValueOnce(new Response('[]', { status: 200 }))
    render(<MemoryRouter><MerchantPage actor={actor} /></MemoryRouter>)
    const btn = await screen.findByRole('button', { name: '批准' })
    await userEvent.click(btn)
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === 'POST')
      expect(post?.[0]).toBe('/api/merchant/tasks/7/resolve')
      expect(JSON.parse((post?.[1] as RequestInit).body as string))
        .toEqual({ decision: 'approved', note: null })
    })
    expect(await screen.findByText(/暂无待审批/)).toBeInTheDocument()
  })

  it('reject asks for a note', async () => {
    const fetchMock = vi.spyOn(global, 'fetch')
      .mockResolvedValueOnce(new Response(JSON.stringify([TASK]), { status: 200 }))
      .mockResolvedValue(new Response(JSON.stringify({ refund_state: 'rejected' }), { status: 200 }))
    render(<MemoryRouter><MerchantPage actor={actor} /></MemoryRouter>)
    await screen.findByText('#A1002')
    await userEvent.click(screen.getByRole('button', { name: '驳回' }))
    await userEvent.type(await screen.findByPlaceholderText(/驳回原因/), '超出退款期限')
    await userEvent.click(screen.getByRole('button', { name: '确认驳回' }))
    await waitFor(() => {
      const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === 'POST')
      expect(JSON.parse((post?.[1] as RequestInit).body as string))
        .toEqual({ decision: 'rejected', note: '超出退款期限' })
    })
  })
})
