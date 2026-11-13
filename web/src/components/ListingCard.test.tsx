import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import type { ListingCard as T } from '../api/types'
import { ListingCard } from './ListingCard'

const base: T = {
  id: 1, title: 'فيلا درج داخلي', property_type: 'villa', price: 1850000, district: 'النرجس', bedrooms: 5,
  bathrooms: 4, built_area_m2: 420, land_area_m2: 312, photo_url: null, score: 82,
  commutes: { school: 12, work: null }, family_status: 'new', first_seen: null, lat: 1, lng: 1, price_drop: null,
}

it('renders price, district, score and commute chips with missing as dash', () => {
  render(<ListingCard listing={base} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.getByText('1,850,000 ر.س')).toBeInTheDocument()
  expect(screen.getByText(/النرجس/)).toBeInTheDocument()
  expect(screen.getByText('82')).toBeInTheDocument()
  expect(screen.getByLabelText('المدرسة: 12 د')).toBeInTheDocument()
  expect(screen.getByLabelText('العمل: —')).toBeInTheDocument()
})

it('buttons call onReact without opening the card', async () => {
  const onOpen = vi.fn(), onReact = vi.fn()
  render(<ListingCard listing={base} onOpen={onOpen} onReact={onReact} />)
  await userEvent.click(screen.getByRole('button', { name: 'حفظ' }))
  await userEvent.click(screen.getByRole('button', { name: 'استبعاد' }))
  expect(onReact.mock.calls).toEqual([['bookmark'], ['reject']])
  expect(onOpen).not.toHaveBeenCalled()
  await userEvent.click(screen.getByRole('article'))
  expect(onOpen).toHaveBeenCalledWith(1)
})

it('bookmarked card shows saved state', () => {
  render(<ListingCard listing={{ ...base, family_status: 'bookmarked' }} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.getByRole('button', { name: 'محفوظ' })).toHaveAttribute('aria-pressed', 'true')
})

it('uses Arabic plural forms for rooms', () => {
  render(<ListingCard listing={{ ...base, bedrooms: 2 }} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.getByText('غرفتان')).toBeInTheDocument()
})
