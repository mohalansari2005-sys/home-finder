import { pluralAr } from './format'
import type { Trip } from '../api/types'

/** Today's calendar date in Asia/Riyadh as "YYYY-MM-DD". */
export const riyadhToday = (now: Date = new Date()): string =>
  new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Riyadh', year: 'numeric', month: '2-digit', day: '2-digit' }).format(now)

/** The next Saturday strictly after today (Riyadh calendar), as "YYYY-MM-DD". */
export function nextSaturday(now: Date = new Date()): string {
  const [y, m, d] = riyadhToday(now).split('-').map(Number)
  const day = new Date(Date.UTC(y, m - 1, d, 12))
  const add = ((6 - day.getUTCDay() + 7) % 7) || 7
  day.setUTCDate(day.getUTCDate() + add)
  return day.toISOString().slice(0, 10)
}

export interface TripWarning { code: string; text: string }

/** Arabic text for the warning codes the server sends; unknown codes are ignored. */
export function tripWarnings(t: Pick<Trip, 'warnings' | 'skipped_no_location'>): TripWarning[] {
  const out: TripWarning[] = []
  for (const code of t.warnings) {
    if (code === 'no_route') out.push({ code, text: 'تعذّر حساب المسار، الترتيب يدوي' })
    else if (code === 'skipped_no_location') {
      const n = t.skipped_no_location ?? 0
      const c = String(n)
      const forms = pluralAr(n, { zero: 'عقارات', one: 'عقار واحد', two: 'عقارين', few: `${c} عقارات`, many: `${c} عقارًا`, other: `${c} عقار` })
      out.push({ code, text: `تم تخطي ${forms} لعدم توفر موقع` })
    } else if (code === 'precheck_pending') out.push({ code, text: 'جارٍ التحقق من الإعلانات' })
  }
  return out
}

export const CONTACT_STATUSES = [
  { value: 'not_contacted', label: 'لم نتواصل' },
  { value: 'contacted', label: 'تم التواصل' },
  { value: 'confirmed', label: 'مؤكد' },
  { value: 'visited', label: 'تمت الزيارة' },
  { value: 'cancelled', label: 'ملغاة' },
] as const

export const TRIP_STATUS_AR: Record<string, string> = { planned: 'مخططة', done: 'تمت', cancelled: 'ملغاة' }

export const MAX_PHOTO_BYTES = 8 * 1024 * 1024
