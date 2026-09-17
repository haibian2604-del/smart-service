import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, request } from './api'
import { saveActor, DEMO_ACTORS } from './actor'

afterEach(() => vi.restoreAllMocks())

describe('request', () => {
  it('injects X-Actor-Id from stored actor', async () => {
    saveActor(DEMO_ACTORS[1])
    const spy = vi.spyOn(global, 'fetch').mockResolvedValue(new Response('[]', { status: 200 }))
    await request('/api/x')
    expect(spy.mock.calls[0][1]!.headers).toBeInstanceOf(Headers)
    expect(new Headers((spy.mock.calls[0][1]!.headers as Headers)).get('X-Actor-Id')).toBe('2')
  })

  it('throws ApiError with status on non-2xx', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue(new Response('no', { status: 404 }))
    const err = await request('/api/x').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(404)
  })
})
