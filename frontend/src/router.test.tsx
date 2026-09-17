import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'
import { AppRoutes } from './router'
import { clearActor, saveActor, DEMO_ACTORS } from './lib/actor'

beforeEach(() => { localStorage.clear(); clearActor() })

describe('role guard', () => {
  it('redirects guest to role picker', () => {
    render(<MemoryRouter initialEntries={['/chat']}><AppRoutes /></MemoryRouter>)
    expect(screen.getByText(/选择身份/)).toBeInTheDocument()
  })

  it('blocks customer from merchant page', () => {
    saveActor({ id: 1, role: 'user', name: '演示用户', merchantId: null })
    render(<MemoryRouter initialEntries={['/merchant']}><AppRoutes /></MemoryRouter>)
    expect(screen.getByText(/无权访问/)).toBeInTheDocument()
  })

  it('allows merchant into merchant page', () => {
    saveActor(DEMO_ACTORS[1])
    render(<MemoryRouter initialEntries={['/merchant']}><AppRoutes /></MemoryRouter>)
    expect(screen.getAllByText(/待审批/).length).toBeGreaterThanOrEqual(1)
  })
})
