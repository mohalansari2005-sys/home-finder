import { describe, expect, it } from 'vitest'
import { formatArea, formatDate, formatRelative, formatMinutes, formatPrice, formatRooms, formatYears, pluralAr, PLACE_LABEL_AR, toDate } from './format'

describe('format', () => {
  it('formats price with western digits and riyal suffix', () => {
    expect(formatPrice(1500000)).toBe('1,500,000 ر.س')
    expect(formatPrice(null)).toBe('السعر غير مذكور')
  })
  it('formats minutes and missing', () => {
    expect(formatMinutes(12)).toBe('12 د')
    expect(formatMinutes(null)).toBe('—')
    expect(formatMinutes(undefined)).toBe('—')
  })
  it('formats area', () => {
    expect(formatArea(312.4)).toBe('312 م²')
    expect(formatArea(null)).toBe('—')
  })
})

describe('pluralAr', () => {
  const forms = { zero: 'z', one: 'o', two: 't', few: 'f', many: 'm', other: 'x' }
  it.each([
    [0, 'z'], [1, 'o'], [2, 't'], [3, 'f'], [10, 'f'], [11, 'm'], [99, 'm'], [100, 'x'], [101, 'x'], [102, 'x'],
    [103, 'f'], [110, 'f'], [111, 'm'], [199, 'm'], [200, 'x'], [1000, 'x'],
  ])('%i -> %s', (n, want) => {
    expect(pluralAr(n, forms)).toBe(want)
  })
  it('formatRooms covers every category', () => {
    expect(formatRooms(0)).toBe('لا توجد غرف')
    expect(formatRooms(1)).toBe('غرفة واحدة')
    expect(formatRooms(2)).toBe('غرفتان')
    expect(formatRooms(3)).toBe('3 غرف')
    expect(formatRooms(103)).toBe('103 غرف')
    expect(formatRooms(11)).toBe('11 غرفة')
    expect(formatRooms(111)).toBe('111 غرفة')
    expect(formatRooms(100)).toBe('100 غرفة')
    expect(formatRooms(null)).toBe('—')
  })
  it('formatYears covers every category', () => {
    expect(formatYears(0)).toBe('جديد')
    expect(formatYears(1)).toBe('سنة واحدة')
    expect(formatYears(2)).toBe('سنتان')
    expect(formatYears(3)).toBe('3 سنوات')
    expect(formatYears(11)).toBe('11 سنة')
    expect(formatYears(100)).toBe('100 سنة')
    expect(formatYears(undefined)).toBe('—')
  })
})

describe('dates', () => {
  it('toDate pins date-only values to 12:00 UTC and rejects invalid', () => {
    expect(toDate('2026-11-15')!.toISOString()).toBe('2026-11-15T12:00:00.000Z')
    expect(toDate('2026-02-31')).toBeNull()
    expect(toDate('nope')).toBeNull()
    expect(toDate('2026-13-01')).toBeNull()
  })
  it('formatDate uses gregorian, western digits, Riyadh time', () => {
    const s = formatDate(toDate('2026-11-15')!)
    expect(s).toMatch(/15/)
    expect(s).toMatch(/2026/)
    expect(s).not.toMatch(/[٠-٩]/)
  })
})

describe('formatRelative', () => {
  const now = new Date('2026-11-13T12:00:00Z')
  const ago = (ms: number) => new Date(now.getTime() - ms)
  const MIN = 60_000, HOUR = 60 * MIN, DAY = 24 * HOUR
  it('uses Arabic plural forms', () => {
    expect(formatRelative(ago(20_000), now)).toBe('الآن')
    expect(formatRelative(ago(MIN), now)).toBe('قبل دقيقة')
    expect(formatRelative(ago(2 * MIN), now)).toBe('قبل دقيقتين')
    expect(formatRelative(ago(5 * MIN), now)).toBe('قبل 5 دقائق')
    expect(formatRelative(ago(2 * HOUR), now)).toBe('قبل ساعتين')
    expect(formatRelative(ago(11 * HOUR), now)).toBe('قبل 11 ساعة')
    expect(formatRelative(ago(DAY), now)).toBe('أمس')
    expect(formatRelative(ago(3 * DAY), now)).toBe('قبل 3 أيام')
  })
  it('falls back to a date after a month', () => {
    expect(formatRelative(ago(45 * DAY), now)).toMatch(/2026/)
  })
})

describe('PLACE_LABEL_AR', () => {
  it('labels every place kind including the current home', () => {
    expect(PLACE_LABEL_AR.home).toBe('المنزل الحالي')
    expect(PLACE_LABEL_AR.school).toBe('المدرسة')
    expect(Object.keys(PLACE_LABEL_AR).sort()).toEqual(['airport', 'home', 'school', 'university', 'work'])
  })
})
