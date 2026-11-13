import type { ListingDetail } from '../api/types'
import type { Breakpoint } from './breakpoint'
import { FACING_AR, formatArea, formatMinutes, formatNumber, formatPrice, formatYears } from './format'

export type Better = 'higher' | 'lower' | null
export type CellValue = number | string | boolean | null

export interface CompareRow {
  key: string
  label: string
  better: Better
  value: (l: ListingDetail) => CellValue
  /** Format a known (non-null) value. Unknown values render as "غير مذكور" in the table. */
  fmt: (v: CellValue) => string
}

const num = (f: (n: number) => string) => (v: CellValue) => f(Number(v))
const yesNo = (v: CellValue) => (v ? 'نعم' : 'لا')

export const COMPARE_ROWS: CompareRow[] = [
  { key: 'price', label: 'السعر', better: 'lower', value: (l) => l.price, fmt: num(formatPrice) },
  { key: 'price_per_m2', label: 'سعر المتر', better: 'lower',
    value: (l) => (l.price != null && l.built_area_m2 ? Math.round(l.price / l.built_area_m2) : null), fmt: (v) => `${formatNumber(Number(v))} ر.س` },
  { key: 'score', label: 'درجة الملاءمة', better: 'higher', value: (l) => l.score, fmt: num((n) => formatNumber(Math.round(n))) },
  { key: 'built_area_m2', label: 'مساحة البناء', better: 'higher', value: (l) => l.built_area_m2, fmt: num(formatArea) },
  { key: 'land_area_m2', label: 'مساحة الأرض', better: 'higher', value: (l) => l.land_area_m2, fmt: num(formatArea) },
  { key: 'bedrooms', label: 'الغرف', better: 'higher', value: (l) => l.bedrooms, fmt: num(formatNumber) },
  { key: 'bathrooms', label: 'دورات المياه', better: 'higher', value: (l) => l.bathrooms, fmt: num(formatNumber) },
  { key: 'building_age_years', label: 'عمر المبنى', better: 'lower', value: (l) => l.building_age_years, fmt: num(formatYears) },
  { key: 'street_width_m', label: 'عرض الشارع', better: 'higher', value: (l) => l.street_width_m, fmt: num((n) => `${formatNumber(n)} م`) },
  { key: 'commute_school', label: 'المدرسة', better: 'lower', value: (l) => l.commutes.school ?? null, fmt: num(formatMinutes) },
  { key: 'commute_work', label: 'العمل', better: 'lower', value: (l) => l.commutes.work ?? null, fmt: num(formatMinutes) },
  { key: 'commute_university', label: 'الجامعة', better: 'lower', value: (l) => l.commutes.university ?? null, fmt: num(formatMinutes) },
  { key: 'commute_airport', label: 'المطار', better: 'lower', value: (l) => l.commutes.airport ?? null, fmt: num(formatMinutes) },
  { key: 'facing', label: 'الواجهة', better: null, value: (l) => l.facing, fmt: (v) => FACING_AR[String(v)] ?? String(v) },
  { key: 'deed_type', label: 'نوع الصك', better: null, value: (l) => l.deed_type, fmt: (v) => String(v) },
  { key: 'has_maid_room', label: 'غرفة خادمة', better: null, value: (l) => l.has_maid_room, fmt: yesNo },
  { key: 'has_driver_room', label: 'غرفة سائق', better: null, value: (l) => l.has_driver_room, fmt: yesNo },
  { key: 'has_yard', label: 'حوش', better: null, value: (l) => l.has_yard, fmt: yesNo },
  { key: 'has_elevator', label: 'مصعد', better: null, value: (l) => l.has_elevator, fmt: yesNo },
]

/** Index of the best value, ignoring nulls. Null when direction is unknown, fewer than 2 values are known, or the top is tied. */
export function bestIndex(values: (number | null)[], better: Better): number | null {
  if (!better) return null
  const known = values.flatMap((v, i) => (v == null ? [] : [{ v, i }]))
  if (known.length < 2) return null
  const best = known.reduce((a, b) => ((better === 'higher' ? b.v > a.v : b.v < a.v) ? b : a))
  return known.filter((k) => k.v === best.v).length > 1 ? null : best.i
}

/** Phone 2, tablet 3, desktop 4. */
export const maxCompare = (bp: Breakpoint): number => (bp === 'phone' ? 2 : bp === 'tablet' ? 3 : 4)

/** "1,2,x,2" -> [1, 2]: positive integers only, no duplicates, order kept. */
export function parseIds(raw: string | null): number[] {
  if (!raw) return []
  const out: number[] = []
  for (const part of raw.split(',')) {
    const n = Number(part)
    if (Number.isInteger(n) && n > 0 && !out.includes(n)) out.push(n)
  }
  return out
}
