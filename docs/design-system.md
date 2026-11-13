# بيتنا: Design System (binding for all `web/` work)

The goal is a calm, trustworthy, content-first tool that a family uses every day on phone, iPad and desktop. Build it from established parts: **no hand-rolled widgets when a shadcn/ui component exists.** The plans' JSX shows structure and behavior; the visual layer comes from this document.

Sources: shadcn/ui + Radix (accessibility primitives), Apple HIG / Material 3 interaction guidance, WCAG 2.2 AA, the `ui-ux-pro-max` guidelines (UX rules), **Anthropic's `frontend-design` skill (visual identity and anti-template critique)**, and `docs/arabic-ui-rules.md` for language and RTL.

## 1. Stack
| Need | Use |
|---|---|
| Components | **shadcn/ui** (Radix base, CLI v4) generated into `web/src/components/ui/` |
| RTL | Initialize shadcn with RTL support if the CLI offers it. Otherwise wrap the app in Radix `DirectionProvider dir="rtl"`, and convert any physical class in generated components (`left/right/ml/mr/pl/pr`) to logical ones. The RTL grep covers `src/components/ui/` too. |
| Icons | **lucide-react** only (shadcn's set). One stroke width (1.75), sizes `size-4` (inline), `size-5` (buttons/nav), `size-6` (empty states). No emoji as icons anywhere. |
| Toasts | **sonner** via shadcn `<Toaster position="top-center" dir="rtl" />` |
| Phone bottom sheets | shadcn **Drawer** (vaul) |
| Side panels (tablet/desktop) | shadcn **Sheet** with `side="left"` (the *end* side in RTL) |
| Dialogs | shadcn **Dialog** / **AlertDialog** (destructive confirms only) |
| Forms | shadcn **Form** = react-hook-form + zod; **Input, Label, Textarea, Select, Checkbox, Switch, Slider, ToggleGroup, RadioGroup** |
| District picker | shadcn **Command** in a **Popover** (combobox with free entry) |
| Dates | shadcn **Calendar** + Popover (`dir="rtl"`, Gregorian, week starts Sunday) |
| Photo gallery | shadcn **Carousel** (Embla), `opts={{ direction: 'rtl' }}` |
| Loading | shadcn **Skeleton** shaped like the content (card skeletons, not spinners, for > 300 ms loads) |
| Tabs / filters | shadcn **Tabs** (views), **ToggleGroup** (chips), **Badge** (status) |
| Score explanation | **Progress** bars inside a **Collapsible** |
| Tooltips | desktop only, never the only way to get information |
| Scroll areas | **ScrollArea** for the chat and panel bodies |

## 2. Identity (after Anthropic's `frontend-design` critique)
**Subject:** a family in Riyadh choosing a home together. The vernacular is Najdi architecture (mud-brick sand tones, deep shade, palm green), street plots and widths, the deed (صك), and drive times through the city. **Audience:** parents and grown children, on phones in the car and on an iPad around the dinner table. **Primary job:** decide quickly whether a house deserves a visit.

**The one memorable element: the fit score as a "seal".** A round sand-colored medallion with the score set large in Kufi numerals, stamped on the photo's start corner (`<ScoreSeal>`), and repeated large in the detail header next to its reasons. Everything else stays quiet.

Avoid these generated-UI tells:
- identical rounded cards with the same grey shadow, one radius on everything, gradient washes
- meta strings joined with «·» (use separate spans with spacing, or icons)
- ALL-CAPS eyebrow labels, and `→` appended to buttons
- a warm cream (#F4F1EA) background or a terracotta accent

## 3. Tokens (shadcn CSS variables, light + dark)
| Name | Role | Light | Dark |
|---|---|---|---|
| Palm | `--primary` (main actions, active nav) | `#1E5A47` | `#5FB394` |
| On palm | `--primary-foreground` | `#FFFFFF` | `#0B2219` |
| Sand | `--seal` (score seal, selected pin, highlights) | `#D8B27A` on ink text | `#C9A26B` |
| Sky | `--accent` (links, map focus, info) | `#2E6A9E` | `#7FB2DE` |
| Ink | `--foreground` | `#1A2027` | `#E9ECEF` |
| Paper | `--background` (neutral, not cream) | `#F6F7F6` | `#12171C` |
| Surface | `--card`, `--popover` | `#FFFFFF` | `#1A2128` |
| Muted | `--muted` / `--muted-foreground` | `#ECEEEC` / `#5B6670` | `#232B33` / `#9AA5AF` |
| Line | `--border` / `--input` | `#DDE1DE` | `#2C353E` |
| `--destructive` | | `#B42318` | `#F97066` |
| `--ring` | | palm | palm (dark) |
| `--warning` (missing data, approximate location) | | `#8A5A00` on `#FFF4DB` | `#F5C76B` on `#3A2C0C` |
| `--success` | | `#1E7A4C` | `#6FCF97` |

- **Radius by hierarchy, not one value:** photos `rounded-2xl`; panels, sheets and drawers `rounded-3xl` (top corners only on phone drawers); buttons and inputs `rounded-xl`; chips and badges `rounded-full`; map pins as pills.
- **Elevation:** listing tiles are **flat** (no shadow): a photo with text below on the paper background, plus a 1px `--border` only when selected. Shadows are reserved for floating layers (sheets, popovers, the map sheet, the phone tab bar) on one scale: `shadow-sm` for floating bars, `shadow-xl` for overlays.
- **Score tiers:** the seal is always sand with the number in ink. The tier is shown by a small ring segment around the seal (palm ≥ 75, sand-dark 50–74, muted < 50) **and** by the number itself, so color is never the only signal.
- Dark mode follows `prefers-color-scheme`. Check contrast in both themes. Text pairs must be ≥ 4.5:1.
- Never put a raw hex in a component. Use token classes only (`bg-primary`, `text-muted-foreground`, …).

## 4. Typography
- **Display: Noto Kufi Arabic** (@fontsource, 600/700). Used for prices, the score seal, page titles and trip times. Its geometric Kufi echoes Saudi signage, so it carries the personality.
- **Body: IBM Plex Sans Arabic** (@fontsource, 400/500/600; `font-display: swap`). Used for everything else. It covers Latin with matching metrics.
- These are clearly distinct roles. Never mix a third family in.
- Scale: 12 (captions only) · 14 (secondary) · **16 body (minimum on phone; inputs ≥ 16px so iOS doesn't zoom)** · 18 (card price) · 20 · 24 (page titles) · 30 (desktop hero numbers).
- Weights: 400 body, 500 labels, 600 titles/prices, 700 sparingly. Never use 800/900 or italic (Arabic gets synthesized).
- Line height 1.6 for Arabic body, 1.3 for headings. Use `text-balance` on short headings.

## 5. Layout and spacing
- 4/8 spacing rhythm (Tailwind's default scale). Card padding `p-4`; section gap `gap-6`; page gutter `px-4 md:px-6 xl:px-8`.
- Navigation:
  - Phone: bottom **tab bar**, ≤ 5 items, each with icon + label, safe-area padding, and an active indicator.
  - iPad: collapsible **sidebar** (shadcn Sidebar, `side="right"` because the start side in RTL is the right).
  - Desktop: fixed sidebar.
  - Never mix patterns at one level.
- Desktop content max width `max-w-7xl`. Long text (descriptions, chat) is capped at about 70 characters per line.
- Use `min-h-dvh`, not `100vh`. Fixed bars reserve padding so content is never hidden behind them.
- Z-index scale: base 0 · sticky 10 · nav 20 · overlay 40 · modal 50 · toast 100.

## 6. Components: look and behavior
- **Listing card:**
  - Flat tile: photo at `aspect-[4/3]` `rounded-2xl`, `object-cover`, `loading="lazy"`, explicit sizes; blur-up placeholder from `bg-muted`.
  - `ScoreSeal` on the photo's start corner; "جديد" (new) and price-drop badges on the end corner.
  - Below the photo: price in Kufi 20/700; then type, district, rooms and area as separate spans with icon or spacing separators (no «·» strings).
  - Commute row: Lucide `School`, `Briefcase`, `GraduationCap`, `Plane` + `<bdi>12 د</bdi>`.
  - Actions: a full-width row of two buttons, ≥ 44px tall; bookmark is `default` when saved and `secondary` when not, reject is `outline`.
- **Buttons:** one primary action per screen. Icon-only buttons are ≥ 44×44 and have an `aria-label`. Async buttons are disabled and show a spinner while pending.
- **Reject:** optimistic remove, plus a sonner toast «تم الاستبعاد» with an **«تراجع»** (undo) action for 5 s. Undo is better than a confirm dialog here.
- **Empty states:** a Lucide icon (size-6, muted), one sentence, one action. For example, an empty feed shows "لا توجد عقارات تطابق تفضيلاتكم بعد" (no listings match your preferences yet) with the button «تعديل التفضيلات» (edit preferences).
- **Errors:** inline under the field (`aria-describedby`), stating the cause and how to fix it. Network errors show a retry button.
- **Detail view:** Carousel gallery with dots + counter «3/12»; facts in a 2-column (phone) or 3-column (≥ md) definition grid; missing values in `warning` style «غير مذكور» (not mentioned).
- **Chat:** user bubble `bg-primary text-primary-foreground` on the start side; assistant bubble `bg-card border` on the end side. Tool status as a muted line with a small spinner. Listing cards render inline in a horizontal ScrollArea.
- **Map pins:** price label pills with tokens; selected pin scaled 1.1 with a ring. The 4 fixed places are Lucide icons in white circles. Legend in a small Card.

## 7. Motion
- Durations: 150 ms for micro feedback (press/hover), 200–250 ms for sheets and drawers entering, 150 ms for exiting. Ease-out on enter, ease-in on exit. Animate only `transform` and `opacity`.
- Press feedback: `active:scale-[0.98]` on cards and buttons. At most 1–2 animated elements per view.
- `motion-reduce:` variants turn off all non-essential motion.

## 8. Accessibility checklist (every PR)
- Visible focus ring (`ring-2 ring-ring ring-offset-2`) on everything interactive; tab order matches visual (RTL) order.
- Every input has a visible `Label` (never placeholder-only); `autocomplete="current-password"` on login; paste allowed.
- Icon-only controls have accessible names; `aria-pressed` / `aria-expanded` / `aria-current="page"` where they apply.
- Don't rely on color alone (scores show numbers, flags show text).
- Toasts use `aria-live="polite"` (sonner does this); focus moves to `<main>` on route change.
- Touch targets ≥ 44px with ≥ 8px spacing; no hover-only actions; no swipe-only actions (carousels have buttons).
- Verify at 375px, 768px portrait, 1024px landscape and 1440px, in both themes.

## 9. Quality bar (each frontend task, before committing)
1. No physical direction classes (RTL grep, including `components/ui`).
2. No raw hex in components; no emoji icons; no `font-black` or italic; no «·»-joined meta strings; no `→` in button labels; listing tiles carry no shadow.
3. Every async view has skeleton, empty and error states.
4. Playwright screenshots at phone/tablet/desktop are saved to `web/test-results/screens/` (gitignored), and the implementer has looked at them for overflow, clipped Arabic text and misalignment.
