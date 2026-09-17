import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { AppRoutes } from './router'

describe('role guard', () => {
  it('redirects guest to role picker', () => {
    render(<MemoryRouter initialEntries={['/chat']}><AppRoutes actor={null} /></MemoryRouter>)
    expect(screen.getByText(/选择身份/)).toBeInTheDocument()
  })

  it('blocks customer from merchant page', () => {
    const actor = { id: 1, role: 'user' as const, name: '演示用户', merchantId: null }
    render(<MemoryRouter initialEntries={['/merchant']}><AppRoutes actor={actor} /></MemoryRouter>)
    expect(screen.getByText(/无权访问/)).toBeInTheDocument()
  })

  it('allows merchant into merchant page', () => {
    const actor = { id: 2, role: 'merchant' as const, name: '青柠数码', merchantId: 1 }
    render(<MemoryRouter initialEntries={['/merchant']}><AppRoutes actor={actor} /></MemoryRouter>)
    expect(screen.getByText(/待审批/)).toBeInTheDocument()
  })
})
