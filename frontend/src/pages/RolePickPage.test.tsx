import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RolePickPage } from './RolePickPage'
import { clearActor, loadActor } from '../lib/actor'

vi.stubGlobal('location', { ...window.location, assign: vi.fn() })

beforeEach(() => { localStorage.clear(); clearActor() })

describe('RolePickPage', () => {
  it('saves actor and hard-navigates on click', () => {
    render(
      <MemoryRouter>
        <RolePickPage />
      </MemoryRouter>,
    )
    fireEvent.click(screen.getByText('青柠数码'))
    expect(loadActor()?.id).toBe(2)                       // 身份已保存
    expect(window.location.assign).toHaveBeenCalledWith('/merchant')  // 整页跳转目标正确
  })
})
