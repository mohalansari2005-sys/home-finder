export type Factor =
  | 'commute_school' | 'commute_work' | 'commute_university' | 'commute_airport' | 'price' | 'built_area' | 'land_area'
  | 'building_age' | 'street_width' | 'facing' | 'street_count' | 'deed_type' | 'bedrooms' | 'bathrooms'
  | 'maid_room' | 'driver_room' | 'yard' | 'elevator'

export const FACTOR_AR: Record<Factor, string> = {
  commute_school: 'القرب من المدرسة', commute_work: 'القرب من العمل', commute_university: 'القرب من الجامعة',
  commute_airport: 'القرب من المطار', price: 'السعر مقارنة بالميزانية', built_area: 'مساحة البناء',
  land_area: 'مساحة الأرض', building_age: 'حداثة البناء', street_width: 'عرض الشارع', facing: 'اتجاه الواجهة',
  street_count: 'عدد الشوارع', deed_type: 'نوع الصك', bedrooms: 'عدد الغرف', bathrooms: 'دورات المياه',
  maid_room: 'غرفة خادمة', driver_room: 'غرفة سائق', yard: 'حوش', elevator: 'مصعد',
}

/** Labels for the preference fields shown in the change history (keys are `section.field`). */
export const FIELD_AR: Record<string, string> = {
  'hard_filters.city': 'المدينة', 'hard_filters.property_types': 'أنواع العقار', 'hard_filters.districts': 'الأحياء',
  'hard_filters.price_max': 'أعلى سعر', 'hard_filters.min_bedrooms': 'أقل عدد غرف',
  'hard_filters.building_age_max': 'أكبر عمر للمبنى', 'hard_filters.street_width_min': 'أقل عرض للشارع',
  'hard_filters.max_commute': 'أقصى مدة وصول',
  'targets.commute_good_min': 'مدة الوصول الممتازة', 'targets.commute_bad_min': 'مدة الوصول السيئة',
  'targets.built_area_ideal': 'مساحة البناء المثالية', 'targets.land_area_ideal': 'مساحة الأرض المثالية',
  'targets.age_bad_years': 'عمر البناء غير المرغوب', 'targets.street_good_m': 'عرض الشارع الجيد',
  'targets.street_bad_m': 'عرض الشارع الضيق', 'targets.preferred_facings': 'الواجهات المفضلة',
  'targets.bedrooms_ideal': 'عدد الغرف المثالي', 'targets.dismissed_suggestions': 'الاقتراحات المرفوضة',
}

export function fieldLabel(key: string): string {
  if (key.startsWith('weights.')) return `أهمية ${FACTOR_AR[key.slice(8) as Factor] ?? key.slice(8)}`
  return FIELD_AR[key] ?? key
}

/** Reject reasons offered in the reason sheet, in display order (labels in REASON_AR). */
export const REJECT_REASONS = ['too_old', 'narrow_street', 'bad_layout', 'overpriced', 'far', 'other'] as const

export const REASON_AR: Record<string, string> = {
  price_above_max: 'السعر أعلى من الميزانية', bedrooms_below_min: 'الغرف أقل من المطلوب', type_excluded: 'نوع العقار غير مطلوب',
  district_excluded: 'خارج الأحياء المختارة', commute_school_too_long: 'بعيد عن المدرسة', commute_work_too_long: 'بعيد عن العمل',
  commute_university_too_long: 'بعيد عن الجامعة', commute_airport_too_long: 'بعيد عن المطار', too_old: 'قديم',
  street_too_narrow: 'الشارع ضيق', narrow_street: 'الشارع ضيق', bad_layout: 'التصميم غير مناسب', overpriced: 'السعر مرتفع',
  far: 'بعيد', other: 'سبب آخر',
}

const DIGITS: Record<string, string> = { '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9', '٫': '.', '،': ',' }

export function parseLatLng(text: string): { lat: number; lng: number } | null {
  const t = text.replace(/[٠-٩٫،]/g, (c) => DIGITS[c])
  const m = t.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/) ?? t.match(/q=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/)
    ?? t.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/)
  if (!m) return null
  const lat = Number(m[1]), lng = Number(m[2])
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null
  return { lat, lng }
}
