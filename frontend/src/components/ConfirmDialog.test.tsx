import { render, screen, fireEvent } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'

describe('ConfirmDialog', () => {
  it('renders message and fires confirm', () => {
    const onConfirm = vi.fn(), onCancel = vi.fn()
    render(<ConfirmDialog open message="将删除该会话" onConfirm={onConfirm} onCancel={onCancel} />)
    expect(screen.getByText('将删除该会话')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '删除' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('cancel button and overlay click close without confirming', () => {
    const onConfirm = vi.fn(), onCancel = vi.fn()
    render(<ConfirmDialog open message="msg" onConfirm={onConfirm} onCancel={onCancel} />)
    fireEvent.click(screen.getByRole('button', { name: '取消' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole('dialog'))
    expect(onCancel).toHaveBeenCalledTimes(2)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('renders nothing when closed', () => {
    render(<ConfirmDialog open={false} message="msg" onConfirm={() => {}} onCancel={() => {}} />)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
