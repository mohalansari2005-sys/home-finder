import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { ScoreBreakdown } from './ScoreBreakdown'

const b = {
  total: 71, missing: ['street_width'],
  contributions: [
    { factor: 'price', value: 1, weight: 1, delta: 8.1 }, { factor: 'commute_work', value: 0.9, weight: 1, delta: 6.5 },
    { factor: 'yard', value: 1, weight: 0.3, delta: 2.4 }, { factor: 'bedrooms', value: 0.6, weight: 0.4, delta: 0.8 },
    { factor: 'building_age', value: 0, weight: 0.6, delta: -4.9 },
  ],
}

it('shows top pluses and minuses then expands', async () => {
  render(<ScoreBreakdown breakdown={b} />)
  expect(screen.getAllByTestId('plus').map((e) => e.textContent)).toEqual(['السعر مقارنة بالميزانية', 'القرب من العمل', 'حوش'])
  expect(screen.getAllByTestId('minus').map((e) => e.textContent)).toEqual(['حداثة البناء'])
  await userEvent.click(screen.getByRole('button', { name: 'كل التفاصيل' }))
  expect(screen.getByText(/بيانات ناقصة/)).toHaveTextContent('عرض الشارع')
})

it('handles no score', () => {
  render(<ScoreBreakdown breakdown={null} />)
  expect(screen.getByText('لا يوجد تقييم بعد')).toBeInTheDocument()
})
