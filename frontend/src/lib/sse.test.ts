import { describe, expect, it } from 'vitest'
import { parseSSEChunk } from './sse'

describe('parseSSEChunk', () => {
  it('parses a single complete event', () => {
    expect(parseSSEChunk('data: {"type":"token","text":"你好"}\n\n').events)
      .toEqual([{ type: 'token', text: '你好' }])
  })

  it('keeps the trailing partial block as buffer', () => {
    const r = parseSSEChunk('data: {"type":"token","text":"a"}\n\ndata: {"type":"tok')
    expect(r.events).toHaveLength(1)
    expect(r.buffer).toBe('data: {"type":"tok')
  })

  it('resumes correctly from a carried buffer', () => {
    const r = parseSSEChunk('en","text":"b"}\n\n', 'data: {"type":"tok')
    expect(r.events).toEqual([{ type: 'token', text: 'b' }])
    expect(r.buffer).toBe('')
  })

  it('ignores malformed json blocks', () => {
    expect(parseSSEChunk('data: {broken\n\n').events).toEqual([])
  })

  it('ignores ping comments', () => {
    expect(parseSSEChunk(': ping\n\n').events).toEqual([])
  })
})
