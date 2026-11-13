import { Briefcase, GraduationCap, Plane, School, type LucideIcon } from 'lucide-react'

// All number/date formatting goes through here (see docs/arabic-ui-rules.md).
// Never call Intl with bare 'ar' / 'ar-SA': digits, percent sign and calendar vary by runtime.
const nf = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 })
const df = new Intl.DateTimeFormat('ar-SA-u-ca-gregory-nu-latn', { dateStyle: 'long', timeZone: 'Asia/Riyadh' })

export const formatPrice = (n: number | null | undefined) => (n == null ? 'السعر غير مذكور' : `${nf.format(n)} ر.س`)
export const formatMinutes = (m: number | null | undefined) => (m == null ? '—' : `${nf.format(m)} د`)
export const formatArea = (m: number | null | undefined) => (m == null ? '—' : `${nf.format(m)} م²`)
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

export const PROPERTY_TYPE_AR: Record<string, string> = { villa: 'فيلا', apartment: 'شقة', floor: 'دور', house: 'بيت' }
export const COMMUTE_ICONS: { kind: 'school' | 'work' | 'university' | 'airport'; Icon: LucideIcon; label: string }[] = [
  { kind: 'school', Icon: School, label: 'المدرسة' },
  { kind: 'work', Icon: Briefcase, label: 'العمل' },
  { kind: 'university', Icon: GraduationCap, label: 'الجامعة' },
  { kind: 'airport', Icon: Plane, label: 'المطار' },
]
export const FACING_AR: Record<string, string> = {
  north: 'شمال', south: 'جنوب', east: 'شرق', west: 'غرب',
  northeast: 'شمالية شرقية', northwest: 'شمالية غربية', southeast: 'جنوبية شرقية', southwest: 'جنوبية غربية',
}
