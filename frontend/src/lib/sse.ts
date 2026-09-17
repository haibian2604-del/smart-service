import type { ChatEvent } from '../types'

/**
 * 解析一个网络分片，保留未闭合的尾部块作为 buffer（SSE 分片边界最常见的 bug 点）。
 */
export function parseSSEChunk(chunk: string, buffer = ''): { events: ChatEvent[]; buffer: string } {
  const data = buffer + chunk
  const blocks = data.split('\n\n')
  const remainder = blocks.pop() ?? ''
  const events: ChatEvent[] = []

  for (const block of blocks) {
    for (const line of block.replace(/\r/g, '').split('\n')) {
      if (!line.startsWith('data:')) continue  // 跳过 event:/id:/: ping 注释行
      try {
        events.push(JSON.parse(line.slice(5).trim()) as ChatEvent)
      } catch {
        // malformed json：忽略
      }
    }
  }
  return { events, buffer: remainder }
}
