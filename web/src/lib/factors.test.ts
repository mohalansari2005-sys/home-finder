import { expect, it } from 'vitest'
import { FACTOR_AR, parseLatLng } from './factors'

it('parses coordinates from text and google maps links', () => {
  expect(parseLatLng('24.7136, 46.6753')).toEqual({ lat: 24.7136, lng: 46.6753 })
  expect(parseLatLng('٢٤٫٧١٣٦، ٤٦٫٦٧٥٣')).toEqual({ lat: 24.7136, lng: 46.6753 })
  expect(parseLatLng('https://www.google.com/maps/place/x/@24.81,46.63,15z')).toEqual({ lat: 24.81, lng: 46.63 })
  expect(parseLatLng('https://maps.google.com/?q=24.8,46.6')).toEqual({ lat: 24.8, lng: 46.6 })
  expect(parseLatLng('hello')).toBeNull()
  expect(parseLatLng('91, 46')).toBeNull()
})

it('has an Arabic label for every factor', () => {
  expect(Object.keys(FACTOR_AR)).toHaveLength(18)
})
