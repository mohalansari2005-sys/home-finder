import { Briefcase, GraduationCap, House, Plane, School, type LucideIcon } from 'lucide-react'

import type { PlaceKind, TextConflicts } from '../api/types'

// All number/date formatting goes through here (see docs/arabic-ui-rules.md).
// Never call Intl with bare 'ar' / 'ar-SA': digits, percent sign and calendar vary by runtime.
const nf = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const df = new Intl.DateTimeFormat('ar-SA-u-ca-gregory-nu-latn', { dateStyle: 'long', timeZone: 'Asia/Riyadh' })

export const formatPrice = (n: number | null | undefined) => (n == null ? 'السعر غير مذكور' : `${nf.format(n)} ر.س`)
export const formatMinutes = (m: number | null | undefined) => (m == null ? '—' : `${nf.format(m)} د`)
export const formatArea = (m: number | null | undefined) => (m == null ? '—' : `${nf.format(m)} م²`)
/** Fixed decimals with Latin digits, e.g. 7.4. */
export const formatDecimal = (n: number | null | undefined, digits = 1) =>
  n == null ? '—' : new Intl.NumberFormat('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n)
export const formatNumber = (n: number | null | undefined) => (n == null ? '—' : nf.format(n))

/** Date-only "YYYY-MM-DD" -> Date pinned to 12:00 UTC (never local midnight). Invalid input -> null. */
export function toDate(s: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s)
  if (!m) return null
  const [y, mo, d] = [Number(m[1]), Number(m[2]), Number(m[3])]
  const date = new Date(Date.UTC(y, mo - 1, d, 12))
  if (date.getUTCFullYear() !== y || date.getUTCMonth() !== mo - 1 || date.getUTCDate() !== d) return null
  return date
}
export const formatDate = (d: Date) => df.format(d)
const dtf = new Intl.DateTimeFormat('ar-SA-u-ca-gregory-nu-latn', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'Asia/Riyadh' })
export const formatDateTime = (d: Date) => dtf.format(d)

const tdf = new Intl.DateTimeFormat('ar-SA-u-ca-gregory-nu-latn', { weekday: 'long', day: 'numeric', month: 'long', timeZone: 'Asia/Riyadh' })
/** "YYYY-MM-DD" -> "السبت، 14 نوفمبر". Invalid input -> ''. */
export function formatTripDate(s: string): string {
  const d = toDate(s)
  return d ? tdf.format(d) : ''
}

/** "16:10" -> { time: '4:10', period: 'م' }. Never show the raw 24-hour string; wrap `time` in <bdi>. */
export function formatClock(hhmm: string | null | undefined): { time: string; period: 'ص' | 'م' } | null {
  const m = hhmm ? /^(\d{1,2}):(\d{2})/.exec(hhmm) : null
  if (!m) return null
  const h = Number(m[1])
  if (h > 23 || Number(m[2]) > 59) return null
  return { time: `${h % 12 || 12}:${m[2]}`, period: h >= 12 ? 'م' : 'ص' }
}

export interface PluralForms { zero: string; one: string; two: string; few: string; many: string; other: string }

/** CLDR Arabic plural categories: 0 / 1 / 2 / n%100 in 3-10 / n%100 in 11-99 / other. */
export function pluralAr(n: number, f: PluralForms): string {
  if (n === 0) return f.zero
  if (n === 1) return f.one
  if (n === 2) return f.two
  const r = n % 100
  if (r >= 3 && r <= 10) return f.few
  if (r >= 11 && r <= 99) return f.many
  return f.other
}

export function formatRooms(n: number | null | undefined): string {
  if (n == null) return '—'
  const c = nf.format(n)
  return pluralAr(n, { zero: 'لا توجد غرف', one: 'غرفة واحدة', two: 'غرفتان', few: `${c} غرف`, many: `${c} غرفة`, other: `${c} غرفة` })
}

export function formatYears(n: number | null | undefined): string {
  if (n == null) return '—'
  const c = nf.format(n)
  return pluralAr(n, { zero: 'جديد', one: 'سنة واحدة', two: 'سنتان', few: `${c} سنوات`, many: `${c} سنة`, other: `${c} سنة` })
}

export const PROPERTY_TYPE_AR: Record<string, string> = { villa: 'فيلا', apartment: 'شقة', floor: 'دور', house: 'بيت', townhouse: 'تاون هاوس' }

/** One Arabic line per place where the ad text contradicts the site's labels. */
export function textConflictLines(tc: TextConflicts | null | undefined): string[] {
  const out: string[] = []
  if (tc?.district) out.push(`نص الإعلان يذكر حي ${tc.district.text}، والموقع يصنّفه في ${tc.district.label}`)
  if (tc?.property_type) {
    const ar = (t: string) => PROPERTY_TYPE_AR[t] ?? t
    out.push(`نص الإعلان يصفه ${ar(tc.property_type.text)}، والموقع يصنّفه ${ar(tc.property_type.label)}`)
  }
  return out
}
export const COMMUTE_ICONS: { kind: 'school' | 'work' | 'university' | 'airport'; Icon: LucideIcon; label: string }[] = [
  { kind: 'school', Icon: School, label: 'المدرسة' },
  { kind: 'work', Icon: Briefcase, label: 'العمل' },
  { kind: 'university', Icon: GraduationCap, label: 'الجامعة' },
  { kind: 'airport', Icon: Plane, label: 'المطار' },
]
export const PLACE_LABEL_AR: Record<PlaceKind, string> = {
  home: 'المنزل الحالي', school: 'المدرسة', work: 'العمل', university: 'الجامعة', airport: 'المطار',
}
/** Saved places in display order; the current home leads (it is the trip starting point, never a commute target). */
export const PLACE_ICONS: { kind: PlaceKind; Icon: LucideIcon; label: string }[] = [
  { kind: 'home', Icon: House, label: PLACE_LABEL_AR.home },
  ...COMMUTE_ICONS,
]
export const FACING_AR: Record<string, string> = {
  north: 'شمال', south: 'جنوب', east: 'شرق', west: 'غرب',
  northeast: 'شمالية شرقية', northwest: 'شمالية غربية', southeast: 'جنوبية شرقية', southwest: 'جنوبية غربية',
}

const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

/** "قبل ساعتين", "أمس", ... Falls back to a Gregorian date after 30 days. */
export function formatRelative(d: Date, now: Date = new Date()): string {
  const diff = Math.max(0, now.getTime() - d.getTime())
  if (diff < MIN) return 'الآن'
  if (diff < HOUR) {
    const n = Math.floor(diff / MIN), c = nf.format(n)
    return `قبل ${pluralAr(n, { zero: '', one: 'دقيقة', two: 'دقيقتين', few: `${c} دقائق`, many: `${c} دقيقة`, other: `${c} دقيقة` })}`
  }
  if (diff < DAY) {
    const n = Math.floor(diff / HOUR), c = nf.format(n)
    return `قبل ${pluralAr(n, { zero: '', one: 'ساعة', two: 'ساعتين', few: `${c} ساعات`, many: `${c} ساعة`, other: `${c} ساعة` })}`
  }
  if (diff < 30 * DAY) {
    const n = Math.floor(diff / DAY), c = nf.format(n)
    if (n === 1) return 'أمس'
    return `قبل ${pluralAr(n, { zero: '', one: 'يوم', two: 'يومين', few: `${c} أيام`, many: `${c} يومًا`, other: `${c} يوم` })}`
  }
  return formatDate(d)
}
