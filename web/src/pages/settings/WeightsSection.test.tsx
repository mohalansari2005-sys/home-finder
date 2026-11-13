import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { WeightsSection } from './WeightsSection'

const prefs = {
  hard_filters: {}, targets: {}, locked_weights: ['price'],
  weights: { commute_school: 1, commute_work: 1, commute_university: 0.6, commute_airport: 0.2, price: 2, built_area: 0.6,
    land_area: 0.4, building_age: 0.6, street_width: 0.5, facing: 0.2, street_count: 0.2, deed_type: 0.3, bedrooms: 0.4,
    bathrooms: 0.3, maid_room: 0.3, driver_room: 0.2, yard: 0.3, elevator: 0.2 },
  defaults: { weights: {}, targets: {} },
}

it('shows lock state and saves a changed weight', () => {
  const save = vi.fn()
  render(<WeightsSection prefs={prefs as never} onSave={save} />)
  expect(screen.getByLabelText('السعر مقارنة بالميزانية (مثبت)')).toBeInTheDocument()
  fireEvent.keyDown(screen.getByRole('slider', { name: 'عرض الشارع' }), { key: 'End' })  // Radix slider is keyboard driven: End = max (3)
  fireEvent.click(screen.getByRole('button', { name: 'حفظ الأهمية' }))
  expect(save).toHaveBeenCalledWith({ weights: { street_width: 3 } })
})

it('unlocks and resets', () => {
  const save = vi.fn()
  render(<WeightsSection prefs={prefs as never} onSave={save} />)
  fireEvent.click(screen.getByRole('button', { name: 'إلغاء تثبيت السعر مقارنة بالميزانية' }))
  expect(save).toHaveBeenCalledWith({ unlock: ['price'] })
  fireEvent.click(screen.getByRole('button', { name: 'استعادة الافتراضي' }))
  expect(save).toHaveBeenCalledWith({ reset_weights: true })
})
