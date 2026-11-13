import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { StarRating } from './StarRating'

it('rates by click and exposes the current value via aria-pressed', async () => {
  const on = vi.fn()
  render(<StarRating value={2} onChange={on} />)
  expect(screen.getByRole('button', { name: '2 من 5' })).toHaveAttribute('aria-pressed', 'true')
  expect(screen.getByRole('button', { name: '3 من 5' })).toHaveAttribute('aria-pressed', 'false')
  await userEvent.click(screen.getByRole('button', { name: '4 من 5' }))
  expect(on).toHaveBeenCalledWith(4)
})

it('is keyboard operable', async () => {
  const on = vi.fn()
  render(<StarRating value={null} onChange={on} />)
  await userEvent.tab()
  await userEvent.keyboard('{Enter}')
  expect(on).toHaveBeenCalledWith(1)
  screen.getByRole('button', { name: '5 من 5' }).focus()
  await userEvent.keyboard(' ')
  expect(on).toHaveBeenCalledWith(5)
})
