import { act, renderHook, waitFor } from '@testing-library/react'
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { useChatStream } from './useChatStream'

function mockXHR(events: object[], status = 200) {
  const body = events.map(e => `data: ${JSON.stringify(e)}\n\n`).join('')
  class FakeXHR {
    responseText = ''
    status = status
    open() {} setRequestHeader() {}
    onprogress: (() => void) | null = null
    onload: (() => void) | null = null
    onerror: (() => void) | null = null
    send() {
      // 模拟分两次到达
      const half = Math.floor(body.length / 2)
      setTimeout(() => { this.responseText = body.slice(0, half); this.onprogress?.() }, 0)
      setTimeout(() => { this.responseText = body; this.onprogress?.(); this.onload?.() }, 10)
    }
  }
  return FakeXHR
}

beforeEach(() => {
  localStorage.setItem('smart-service.actor', JSON.stringify({ id: 1, role: 'user', name: 't', merchantId: null }))
})
afterEach(() => vi.restoreAllMocks())

describe('useChatStream', () => {
  it('appends user and assistant messages from SSE stream', async () => {
    vi.stubGlobal('XMLHttpRequest', mockXHR([
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
    vi.stubGlobal('XMLHttpRequest', mockXHR([], 500))
    const { result } = renderHook(() => useChatStream(null))
    await act(() => result.current.send('hi'))
    await waitFor(() => expect(result.current.streaming).toBe(false))
    expect(result.current.messages[1].content).toContain('HTTP 500')
  })
})
