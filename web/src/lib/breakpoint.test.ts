import { expect, it } from 'vitest'
import { getBreakpoint } from './breakpoint'

it('maps widths to breakpoints', () => {
  expect(getBreakpoint(390)).toBe('phone')
  expect(getBreakpoint(767)).toBe('phone')
  expect(getBreakpoint(768)).toBe('tablet')
  expect(getBreakpoint(1199)).toBe('tablet')
  expect(getBreakpoint(1200)).toBe('desktop')
})
