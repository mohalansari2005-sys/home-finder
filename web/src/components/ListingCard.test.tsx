import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import type { ListingCard as T } from '../api/types'
import { ListingCard } from './ListingCard'

const base: T = {
  id: 1, title: 'فيلا درج داخلي', property_type: 'villa', price: 1850000, district: 'النرجس', bedrooms: 5,
  bathrooms: 4, built_area_m2: 420, land_area_m2: 312, photo_url: null, score: 82,
  commutes: { school: 12, work: null }, family_status: 'new', first_seen: null, lat: 1, lng: 1, price_drop: null, status: 'active', whatsapp_url: null, text_conflicts: {},
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

it('a visited listing counts as saved and cannot be un-saved (that would erase the visit)', async () => {
  const onReact = vi.fn()
  render(<ListingCard listing={{ ...base, family_status: 'visited' }} onOpen={() => {}} onReact={onReact} />)
  const b = screen.getByRole('button', { name: 'محفوظ' })
  expect(b).toHaveAttribute('aria-pressed', 'true')
  expect(b).toBeDisabled()
  await userEvent.click(b)
  expect(onReact).not.toHaveBeenCalled()
})

it('uses Arabic plural forms for rooms', () => {
  render(<ListingCard listing={{ ...base, bedrooms: 2 }} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.getByText('غرفتان')).toBeInTheDocument()
})

it('shows a muted removed chip only when the listing was removed', () => {
  const { rerender } = render(<ListingCard listing={base} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.queryByText('الإعلان محذوف')).toBeNull()
  rerender(<ListingCard listing={{ ...base, status: 'removed' }} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.getByText('الإعلان محذوف')).toBeInTheDocument()
  rerender(<ListingCard listing={{ ...base, status: 'stale' }} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.queryByText('الإعلان محذوف')).toBeNull()
})

it('shows the price-drop badge with the amount and the old price struck through', () => {
  const drop = { from: 2000000, to: 1850000, at: '2026-11-01T10:00:00Z' }
  const { rerender } = render(<ListingCard listing={base} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.queryByTestId('price-drop')).toBeNull()
  expect(document.querySelector('del')).toBeNull()
  rerender(<ListingCard listing={{ ...base, price_drop: drop }} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.getByTestId('price-drop')).toHaveTextContent('انخفض 150,000 ر.س')
  expect(screen.getByTestId('price-drop').querySelector('bdi')).toHaveTextContent('150,000')
  expect(document.querySelector('del')).toHaveTextContent('2,000,000 ر.س')
  expect(screen.getByText('1,850,000 ر.س')).toBeInTheDocument()
})

it('compare toggle only shows in compare mode and does not open the card', async () => {
  const onOpen = vi.fn(), onToggle = vi.fn()
  const { rerender } = render(<ListingCard listing={base} onOpen={onOpen} onReact={() => {}} />)
  expect(screen.queryByRole('button', { name: 'قارن' })).toBeNull()
  rerender(<ListingCard listing={base} onOpen={onOpen} onReact={() => {}} compareMode compareSelected={false} onCompareToggle={onToggle} />)
  const btn = screen.getByRole('button', { name: 'قارن' })
  expect(btn).toHaveAttribute('aria-pressed', 'false')
  await userEvent.click(btn)
  expect(onToggle).toHaveBeenCalledTimes(1)
  expect(onOpen).not.toHaveBeenCalled()
  rerender(<ListingCard listing={base} onOpen={onOpen} onReact={() => {}} compareMode compareSelected onCompareToggle={onToggle} />)
  expect(screen.getByRole('button', { name: 'قارن' })).toHaveAttribute('aria-pressed', 'true')
})

it('whatsapp shortcut opens the seller chat without opening the card, and is hidden without a number', async () => {
  const onOpen = vi.fn()
  const url = 'https://wa.me/966500000000?text=x'
  const { rerender } = render(<ListingCard listing={{ ...base, whatsapp_url: url }} onOpen={onOpen} onReact={() => {}} />)
  const link = screen.getByRole('link', { name: 'مراسلة المعلن عبر واتساب' })
  expect(link).toHaveAttribute('href', url)
  expect(link).toHaveAttribute('target', '_blank')
  link.addEventListener('click', (e) => e.preventDefault())  // jsdom cannot navigate
  await userEvent.click(link)
  expect(onOpen).not.toHaveBeenCalled()
  rerender(<ListingCard listing={base} onOpen={onOpen} onReact={() => {}} />)
  expect(screen.queryByRole('link', { name: 'مراسلة المعلن عبر واتساب' })).toBeNull()
})

it('a listing the family already opened is tagged as viewed; new ones are not', () => {
  const { rerender } = render(<ListingCard listing={{ ...base, family_status: 'seen' }} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.getByText('تمت المشاهدة')).toBeInTheDocument()
  rerender(<ListingCard listing={base} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.queryByText('تمت المشاهدة')).toBeNull()
})

it('warns when the ad text names another district or type', () => {
  render(<ListingCard listing={{ ...base, text_conflicts: {
    district: { label: 'النرجس', text: 'القيروان' }, property_type: { label: 'villa', text: 'townhouse' } } }}
    onOpen={() => {}} onReact={() => {}} />)
  expect(screen.getByText('نص الإعلان يذكر حي القيروان، والموقع يصنّفه في النرجس')).toBeInTheDocument()
  expect(screen.getByText('نص الإعلان يصفه تاون هاوس، والموقع يصنّفه فيلا')).toBeInTheDocument()
})

it('shows no warning without conflicts', () => {
  render(<ListingCard listing={base} onOpen={() => {}} onReact={() => {}} />)
  expect(screen.queryByText(/نص الإعلان/)).toBeNull()
})
