# Arabic UI Rules (binding for all `web/` work)

Adapted from the generic RTL and Arabic-copy guidance in the owner's local skills. The Wakil brand itself (colors, logo, Expo Arabic font) does **not** apply. This is a personal project: keep the teal palette and IBM Plex Sans Arabic.

## Numbers, money, dates
- **Never call `Intl` with bare `'ar-SA'` or `'ar'`.** Depending on the runtime and ICU version, it prints Arabic-Indic digits, `٪`, «ر.س.» with a trailing period, and sometimes Hijri dates. All formatting goes through `web/src/lib/format.ts`, which uses `Intl.NumberFormat('en-US')` for digits and `'ar-SA-u-ca-gregory-nu-latn'` for dates.
- Use Western digits `0–9`, `%`, and money as `1,500 ر.س` (amount first, no trailing period). Areas use `م²` only where the font has the glyph, otherwise `م2`.
- **Date-only values** (a trip date, `"YYYY-MM-DD"`) are never built as a local midnight. Pin them to 12:00 UTC (`toDate()` in format.ts). Instants are formatted in `Asia/Riyadh`.

## RTL and mixed script
- `<html lang="ar" dir="rtl">`; logical utilities only (`ms/me/ps/pe/start/end/text-start/text-end`). This is already in the Global Constraints.
- Numbers, phone numbers, prices and Latin words inside Arabic text are **LTR islands**: wrap only the digits in `<bdi>` (or `<span class="num">`). **Never** put `dir="ltr"` / `direction: ltr` on a whole card, cell or tile, because that flips `end` alignment and moves «ر.س» to the wrong side.
- Mirror directional icons (back/next chevrons, "←/→" arrows) in RTL. Timelines and step lists start on the **right**.
- Scrollable tables and grids inside flex/grid parents need `min-w-0`, otherwise phone layouts overflow.

## Copy
- **Plurals:** never build them by string concatenation like `${n} غرف`. Use `pluralAr(n, forms)` from format.ts. Arabic has six categories: zero, one, two, few (3–10), many (11–99), other (100+).
  - غرفة: لا توجد غرف · غرفة واحدة · غرفتان · 3 غرف · 11 غرفة · 100 غرفة
  - سنة: جديد · سنة واحدة · سنتان · 3 سنوات · 11 سنة · 100 سنة
  - عقار: لا توجد عقارات · عقار واحد · عقاران · 3 عقارات · 11 عقارًا · 100 عقار
  - دقيقة (long form): دقيقة واحدة · دقيقتان · 3 دقائق · 11 دقيقة · 100 دقيقة. Chips keep the short `12 د`.
- In empty states, prefer a sentence over a «0 …» count.
- **Buttons use the verbal noun** (gender-neutral): «حفظ», «استبعاد», «إضافة», «إنشاء الرحلة», «مقارنة». Not imperatives like «احفظ» or «أضف».
- Watch hamzas: إضافة، إلغاء، أسعار، إدارة (not اضافة/الغاء/اسعار/ادارة).
- **Typed symbols** (`✓ ✕ → ← ↓ ↗ ★ ²`) may be missing from the Arabic font and render in a fallback face. Use lucide-react icons for every icon (see `docs/design-system.md`). No emoji as icons.
