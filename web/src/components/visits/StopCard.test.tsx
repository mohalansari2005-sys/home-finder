import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router'
import { expect, it, vi } from 'vitest'
import type { TripStop } from '../../api/types'
import { StopCard } from './StopCard'

const stop: TripStop = {
  id: 7, position: 0, eta_local: '16:10', etd_local: '16:40', drive_min: 10, contact_status: 'not_contacted', rating: null,
  notes: null, flags: ['price_changed'], old_price: 2_050_000, whatsapp_url: 'https://wa.me/966551234567?text=x', phone: '966551234567', photos: [],
  listing: { id: 1, title: 'فيلا', price: 1900000, district: 'النرجس', photo_url: null, commutes: {}, score: 80, property_type: 'villa', bedrooms: 5,
    status: 'active' } as never,
}
const view = (s: TripStop, p: Partial<React.ComponentProps<typeof StopCard>> = {}) =>
  render(<MemoryRouter><ol><StopCard stop={s} onPatch={vi.fn()} onUpload={vi.fn()} {...p} /></ol></MemoryRouter>)

it('shows 12-hour times as number islands, flags, whatsapp, and updates status via radio semantics', async () => {
  const onPatch = vi.fn()
  view(stop, { onPatch })
  const range = screen.getByTestId('stop-time')
  expect(range).toHaveTextContent('4:10 – 4:40 م')
  expect(range.querySelectorAll('bdi')).toHaveLength(2)
  expect(screen.queryByText(/16:10/)).toBeNull()
  expect(screen.getByText(/تغيّر السعر من/)).toBeInTheDocument()
  expect(screen.getByText('2,050,000')).toBeInTheDocument()
  expect(screen.getByRole('link', { name: 'مراسلة المعلن عبر واتساب' })).toHaveAttribute('href', stop.whatsapp_url)
  expect(screen.getByRole('radio', { name: 'لم نتواصل' })).toBeChecked()
  await userEvent.click(screen.getByRole('radio', { name: 'تمت الزيارة' }))
  expect(onPatch).toHaveBeenCalledWith({ contact_status: 'visited' })
  expect(screen.queryByRole('button', { name: '1 من 5' })).toBeNull() // rating appears only once visited
})

it('hides whatsapp without a url and marks removed listings', () => {
  view({ ...stop, whatsapp_url: null, phone: null, flags: ['removed'] })
  expect(screen.queryByRole('link', { name: 'مراسلة المعلن عبر واتساب' })).toBeNull()
  expect(screen.getByText('الإعلان محذوف')).toBeInTheDocument()
})

it('shows rating, notes and photo input once visited; notes save on blur only when changed', async () => {
  const onPatch = vi.fn()
  view({ ...stop, contact_status: 'visited', notes: 'قديم' }, { onPatch })
  await userEvent.click(screen.getByRole('button', { name: '5 من 5' }))
  expect(onPatch).toHaveBeenCalledWith({ rating: 5 })
  const notes = screen.getByLabelText('ملاحظات الزيارة')
  await userEvent.click(notes)
  await userEvent.tab()
  expect(onPatch).toHaveBeenCalledTimes(1) // unchanged note is not re-saved
  await userEvent.type(notes, ' جديد')
  await userEvent.tab()
  expect(onPatch).toHaveBeenLastCalledWith({ notes: 'قديم جديد' })
  const input = screen.getByLabelText('إضافة صورة') as HTMLInputElement
  expect(input).toHaveAttribute('accept', 'image/*')
  expect(input).toHaveAttribute('capture', 'environment')
})

it('rejects photos over 8 MB on the client', async () => {
  const onUpload = vi.fn()
  view({ ...stop, contact_status: 'visited' }, { onUpload })
  const input = screen.getByLabelText('إضافة صورة')
  const big = new File([new Uint8Array(8 * 1024 * 1024 + 1)], 'big.jpg', { type: 'image/jpeg' })
  await userEvent.upload(input, big)
  expect(onUpload).not.toHaveBeenCalled()
  expect(await screen.findByText('حجم الصورة يتجاوز 8 ميغابايت')).toBeInTheDocument()
  const ok = new File(['x'], 'ok.jpg', { type: 'image/jpeg' })
  await userEvent.upload(input, ok)
  expect(onUpload).toHaveBeenCalledWith(ok)
})
