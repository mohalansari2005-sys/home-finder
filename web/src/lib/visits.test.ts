import { describe, expect, it } from 'vitest'
import { ApiError } from '../api/client'
import { nextSaturday, photoUploadError, tripWarnings } from './visits'

describe('nextSaturday', () => {
  it('returns the coming Saturday, never today unless it is already past Saturday', () => {
    expect(nextSaturday(new Date('2026-11-13T09:00:00Z'))).toBe('2026-11-14') // Friday -> next day
    expect(nextSaturday(new Date('2026-11-14T09:00:00Z'))).toBe('2026-11-21') // Saturday -> the following one
    expect(nextSaturday(new Date('2026-11-15T09:00:00Z'))).toBe('2026-11-21') // Sunday
  })
  it('uses the Riyadh calendar day', () => {
    expect(nextSaturday(new Date('2026-11-13T22:00:00Z'))).toBe('2026-11-21') // already Saturday 01:00 in Riyadh
  })
})

describe('tripWarnings', () => {
  it('maps known codes to Arabic and ignores unknown ones', () => {
    const w = tripWarnings({ warnings: ['no_route', 'weird', 'skipped_no_location', 'precheck_pending'], skipped_no_location: 2 })
    expect(w.map((x) => x.code)).toEqual(['no_route', 'skipped_no_location', 'precheck_pending'])
    expect(w[0].text).toBe('تعذّر حساب المسار، الترتيب يدوي')
    expect(w[1].text).toBe('تم تخطي عقارين لعدم توفر موقع')
  })
})

describe('photoUploadError', () => {
  it('explains a 413 (proxy body limit) and keeps the generic text otherwise', () => {
    expect(photoUploadError(new ApiError(413, '<html>'))).toBe('حجم الصورة أكبر من 8 ميغابايت')
    expect(photoUploadError(new ApiError(500, 'x'))).toBe('تعذّر رفع الصورة. حاولوا مرة أخرى.')
    expect(photoUploadError(new Error('offline'))).toBe('تعذّر رفع الصورة. حاولوا مرة أخرى.')
  })
})
