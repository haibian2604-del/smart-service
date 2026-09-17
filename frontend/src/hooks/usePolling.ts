import { useEffect, useRef } from 'react'

/**
 * enabled 期间按间隔轮询 fn；fn 返回 true 表示达成条件并自动停止。
 */
export function usePolling(fn: () => Promise<boolean>, intervalMs: number, enabled: boolean) {
  const fnRef = useRef(fn)
  fnRef.current = fn

  useEffect(() => {
    if (!enabled) return
    let stopped = false
    let timer: ReturnType<typeof setTimeout>

    const tick = async () => {
      try {
        if (await fnRef.current()) return  // 达成条件，停止
      } catch { /* 网络抖动：下个周期重试 */ }
      if (!stopped) timer = setTimeout(tick, intervalMs)
    }
    tick()

    return () => { stopped = true; clearTimeout(timer) }
  }, [enabled, intervalMs])
}
