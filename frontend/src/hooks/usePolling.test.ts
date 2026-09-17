import { describe, expect, it, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { usePolling } from './usePolling'

describe('usePolling', () => {
  it('does not poll when disabled', () => {
    const fn = vi.fn()
    renderHook(() => usePolling(fn, 50, false))
    expect(fn).not.toHaveBeenCalled()
  })

  it('stops polling once predicate returns true', async () => {
    const fn = vi.fn().mockResolvedValueOnce(false).mockResolvedValueOnce(false).mockResolvedValue(true)
    renderHook(() => usePolling(fn, 10, true))
    await waitFor(() => expect(fn.mock.calls.length).toBeGreaterThanOrEqual(3))
    const count = fn.mock.calls.length
    await new Promise(r => setTimeout(r, 50))
    expect(fn.mock.calls.length).toBe(count)
  })
})
