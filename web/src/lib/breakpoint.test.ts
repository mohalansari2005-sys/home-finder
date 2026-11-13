import { expect, it } from 'vitest'
import { getBreakpoint, getChatLayout } from './breakpoint'

it('maps widths to breakpoints', () => {
  expect(getBreakpoint(390)).toBe('phone')
  expect(getBreakpoint(767)).toBe('phone')
  expect(getBreakpoint(768)).toBe('tablet')
  expect(getBreakpoint(1199)).toBe('tablet')
  expect(getBreakpoint(1200)).toBe('desktop')
})

it('docks the chat only from 1440px', () => {
  expect(getChatLayout(390)).toBe('page')
  expect(getChatLayout(820)).toBe('overlay')
  expect(getChatLayout(1280)).toBe('overlay')
  expect(getChatLayout(1439)).toBe('overlay')
  expect(getChatLayout(1440)).toBe('docked')
})
