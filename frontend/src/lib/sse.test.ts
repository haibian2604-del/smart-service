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

  it('parses CRLF payload from sse-starlette', () => {
    const { events } = parseSSEChunk('event: message\r\ndata: {"type":"token","text":"hi"}\r\n\r\n', '')
    expect(events).toEqual([{ type: 'token', text: 'hi' }])
  })

  it('handles CRLF split across chunk boundary', () => {
    const first = parseSSEChunk('data: {"type":"token","text":"a"}\r\n', '')
    expect(first.events).toEqual([])
    const second = parseSSEChunk('\r\ndata: {"type":"done"}\r\n\r\n', first.buffer)
    expect(second.events).toEqual([{ type: 'token', text: 'a' }, { type: 'done' }])
  })
})
