import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MessageBubble } from './MessageBubble'

describe('MessageBubble', () => {
  it('renders user text', () => {
    render(<MessageBubble role="user" content="有耳机吗" widgets={[]} toolCalls={[]} />)
    expect(screen.getByText('有耳机吗')).toBeInTheDocument()
  })

  it('renders tool call trace for assistant turn', () => {
    render(<MessageBubble role="assistant" content="已查到" widgets={[]}
      toolCalls={[{ name: 'search_products', args: { keyword: '耳机' } }]} />)
    expect(screen.getByText('search_products')).toBeInTheDocument()
  })

  it('renders empty content while streaming without crash', () => {
    const { container } = render(
      <MessageBubble role="assistant" content="" widgets={[]} toolCalls={[]} streaming />)
    expect(container.querySelector('.animate-pulse')).toBeTruthy()
  })
})
