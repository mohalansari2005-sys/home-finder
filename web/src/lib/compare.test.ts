import { expect, it } from 'vitest'
import { bestIndex, COMPARE_ROWS, maxCompare, parseIds } from './compare'

it('picks best by direction ignoring nulls and ties', () => {
  expect(bestIndex([3, 1, 2], 'lower')).toBe(1)
  expect(bestIndex([3, null, 5], 'higher')).toBe(2)
  expect(bestIndex([2, 2], 'higher')).toBeNull()
  expect(bestIndex([null, 4], 'higher')).toBeNull()
  expect(bestIndex([1, 2], null)).toBeNull()
})

it('ties at the top are no winner, ties below the top are fine', () => {
  expect(bestIndex([5, 5, 1], 'higher')).toBeNull()
  expect(bestIndex([5, 1, 1], 'higher')).toBe(0)
})

it('limits by device', () => {
  expect(maxCompare('phone')).toBe(2)
  expect(maxCompare('tablet')).toBe(3)
  expect(maxCompare('desktop')).toBe(4)
})

it('parses the ids param safely', () => {
  expect(parseIds('1,2,x,2,3')).toEqual([1, 2, 3])
  expect(parseIds(null)).toEqual([])
})

it('has the required rows', () => {
  const keys = COMPARE_ROWS.map((r) => r.key)
  for (const k of ['price', 'score', 'built_area_m2', 'land_area_m2', 'building_age_years', 'street_width_m', 'bedrooms', 'bathrooms', 'facing', 'deed_type'])
    expect(keys).toContain(k)
  expect(COMPARE_ROWS.find((r) => r.key === 'price')?.better).toBe('lower')
})
