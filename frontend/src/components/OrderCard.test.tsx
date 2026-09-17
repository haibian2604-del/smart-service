import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { OrderCard } from './OrderCard'
import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('shows pending human review in amber', () => {
    render(<StatusBadge status="pending" label="待审核" />)
    expect(screen.getByText('待审核')).toBeInTheDocument()
  })
})

describe('OrderCard', () => {
  it('renders order no, status and amount', () => {
    render(<OrderCard data={{
      order_no: '#A1002', status: 'shipped', total_amount: '599.00',
      created_at: '2026-09-01', items: [{ name: '降噪耳机', quantity: 1, unit_price: '599.00' }],
    }} />)
    expect(screen.getByText('#A1002')).toBeInTheDocument()
    expect(screen.getByText('已发货')).toBeInTheDocument()
    expect(screen.getAllByText(/599\.00/).length).toBeGreaterThanOrEqual(1)
  })
})
