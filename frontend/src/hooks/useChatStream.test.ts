import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { useChatStream } from './useChatStream'

function sseResponse(events: object[]) {
  const body = events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('')
  const stream = new ReadableStream({
    start(c) { c.enqueue(new TextEncoder().encode(body)); c.close() },
  })
  return new Response(stream, { status: 200 })
}

beforeEach(() => {
  localStorage.setItem('smart-service.actor', JSON.stringify({ id: 1, role: 'user', name: 't', merchantId: null }))
})
afterEach(() => vi.restoreAllMocks())

describe('useChatStream', () => {
  it('appends user and assistant messages from SSE stream', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(sseResponse([
      { type: 'meta', conversation_id: 9 },
      { type: 'token', text: '为您找到' },
      { type: 'token', text: '以下商品' },
      { type: 'widget', kind: 'product_list', data: [] },
      { type: 'done', conversation_id: 9 },
    ]))
    const { result } = renderHook(() => useChatStream(null))
    await act(() => result.current.send('有耳机吗'))
    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.messages).toHaveLength(2)
    expect(result.current.messages[1].role).toBe('assistant')
    expect(result.current.messages[1].content).toBe('为您找到以下商品')
    expect(result.current.conversationId.current).toBe(9)
  })

  it('shows connection error as assistant message', async () => {
    vi.spyOn(global, 'fetch').mockRejectedValue(new Error('proxy down'))
    const { result } = renderHook(() => useChatStream(null))
    await act(() => result.current.send('hi'))
    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.messages[1].content).toContain('连接失败')
  })
})
