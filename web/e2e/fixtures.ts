import type { Page } from '@playwright/test'

export const card = (id: number, extra: Record<string, unknown> = {}) => ({
  id, title: `فيلا ${id}`, property_type: 'villa', price: 1_500_000 + id, district: 'النرجس', bedrooms: 5, bathrooms: 4,
  built_area_m2: 400, land_area_m2: 300, photo_url: null, score: 70, commutes: { school: 10, work: 20 },
  family_status: 'new', first_seen: null, lat: 24.8, lng: 46.6, price_drop: null, status: 'active', ...extra,
})

const WEIGHTS = { commute_school: 1, commute_work: 1, commute_university: 0.6, commute_airport: 0.2, price: 1, built_area: 0.6,
  land_area: 0.4, building_age: 0.6, street_width: 0.5, facing: 0.2, street_count: 0.2, deed_type: 0.3, bedrooms: 0.4,
  bathrooms: 0.3, maid_room: 0.3, driver_room: 0.2, yard: 0.3, elevator: 0.2 }

const detailOf = (id: number) => ({ ...card(id), description: 'وصف', livings: 2, building_age_years: null, street_width_m: 20,
  facing: 'north', street_count: 1, deed_type: null, has_maid_room: true, has_driver_room: null, has_yard: null,
  has_elevator: null, geo_precision: 'exact', photos: [], sources: [], price_history: [], score_breakdown: null,
  status: 'active', passes_filters: true, filter_reasons: [] })

const sse = (events: object[]) => events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join('')
const BUDGET = 'تم الوصول إلى الحد الشهري لاستخدام المساعد'

/** Scripted assistant replies, keyed by what the test types (events follow docs m3-contract: thread first, done last). */
export function chatEvents(message: string): object[] {
  if (message.includes('حد')) return [{ type: 'thread', thread_id: 't-budget' }, { type: 'error', message: BUDGET }, { type: 'done' }]
  if (message.includes('الميزانية')) {
    return [{ type: 'thread', thread_id: 't-prefs' }, { type: 'tool', name: 'update_preferences' }, { type: 'prefs_changed' },
      { type: 'token', text: 'حدّثت ' }, { type: 'token', text: 'الميزانية.' }, { type: 'done' }]
  }
  return [{ type: 'thread', thread_id: 't-1' }, { type: 'tool', name: 'search_listings' },
    { type: 'listings', items: [card(1, { price_drop: { from: 1_600_000, to: 1_500_001, at: '2026-11-10T00:00:00Z' } }), card(2, { district: 'الياسمين', score: 81 })] },
    { type: 'token', text: 'وجدت ' }, { type: 'token', text: 'فيلتين مناسبتين.' }, { type: 'done' }]
}

export async function mockApi(page: Page, opts: { loggedIn?: boolean; breakdown?: unknown; paused?: boolean; chatNoKey?: boolean; chatDropFirst?: boolean; cardExtras?: Record<number, Record<string, unknown>>; noSuggestions?: boolean; cardCount?: number; learnerChange?: boolean } = {}) {
  let loggedIn = opts.loggedIn ?? false
  const statuses = new Map<number, string>()
  const prefs = {
    hard_filters: { city: 'الرياض', property_types: ['villa'], districts: [] as string[], price_max: null, min_bedrooms: null,
      max_commute: {}, building_age_max: null, street_width_min: null } as Record<string, unknown>,
    weights: { ...WEIGHTS } as Record<string, number>, targets: {} as Record<string, unknown>, locked_weights: [] as string[],
    defaults: { weights: WEIGHTS, targets: {} },
  }
  let places: unknown[] = []
  let adapterPaused = !!opts.paused
  let chatCalls = 0
  const changes: unknown[] = opts.learnerChange
    ? [{ at: new Date().toISOString(), source: 'learner', explanation: 'زادت أهمية عرض الشارع بناءً على تفاعلكم مع العقارات.',
        diff: { 'weights.street_width': { from: 0.5, to: 0.6 } } }]
    : []
  const suggestion = { code: 'too_old', reason: 'too_old', count: 5, patch: { hard_filters: { building_age_max: 21 } },
    text: 'رفضتم 5 عقارات لأنها قديمة. هل نستبعد العقارات الأقدم من 21 سنة؟' }
  let suggestions: unknown[] = opts.noSuggestions ? [] : [suggestion]
  const state = { reacts: [] as Record<string, unknown>[], suggestionCalls: [] as string[] }
  await page.route('**/api/**', async (route) => {
    const url = new URL(route.request().url())
    const m = route.request().method()
    const json = (b: unknown, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(b) })
    if (url.pathname === '/api/login') {
      const ok = JSON.parse(route.request().postData() ?? '{}').password === 'secret'
      if (ok) loggedIn = true
      return route.fulfill({ status: ok ? 204 : 401 })
    }
    if (!loggedIn) return json({ detail: 'login required' }, 401)
    if (url.pathname === '/api/me') return json({ ok: true })
    if (url.pathname === '/api/chat' && m === 'POST') {
      if (opts.chatNoKey) return json({ detail: 'assistant not configured' }, 503)
      if (opts.chatDropFirst && chatCalls++ === 0) return route.abort('failed')
      const message = JSON.parse(route.request().postData() ?? '{}').message as string
      return route.fulfill({ status: 200, contentType: 'text/event-stream', headers: { 'cache-control': 'no-cache' }, body: sse(chatEvents(message)) })
    }
    if (url.pathname === '/api/chat/threads') return json([])
    if (url.pathname === '/api/feed') {
      const items = Array.from({ length: opts.cardCount ?? 2 }, (_, i) => card(i + 1, opts.cardExtras?.[i + 1])).map((c) => ({ ...c, family_status: statuses.get(c.id) ?? c.family_status }))
        .filter((c) => c.family_status !== 'rejected')
      return json({ items, next_offset: null })
    }
    const react = url.pathname.match(/^\/api\/listings\/(\d+)\/react$/)
    if (react && m === 'POST') {
      const body = JSON.parse(route.request().postData() ?? '{}')
      state.reacts.push({ id: Number(react[1]), ...body })
      const kind = body.kind
      const st = kind === 'bookmark' ? 'bookmarked' : kind === 'reject' ? 'rejected' : 'seen'
      statuses.set(Number(react[1]), st)
      return json({ family_status: st })
    }
    if (url.pathname === '/api/suggestions') return json(suggestions)
    const sug = url.pathname.match(/^\/api\/suggestions\/([^/]+)\/(apply|dismiss)$/)
    if (sug && m === 'POST') {
      state.suggestionCalls.push(`${sug[2]}:${sug[1]}`)
      suggestions = suggestions.filter((x) => (x as { code: string }).code !== sug[1])
      return sug[2] === 'apply' ? json({ ok: true }) : route.fulfill({ status: 204 })
    }
    if (url.pathname === '/api/compare') {
      const ids = (url.searchParams.get('ids') ?? '').split(',').map(Number).filter(Boolean)
      if (ids.length < 2 || ids.length > 4) return json({ detail: 'need 2-4 listings' }, 422)
      return json(ids.map((i) => ({ ...detailOf(i), building_age_years: i === 1 ? null : 2 * i, street_width_m: 20 + 5 * i,
        bedrooms: 3 + i, bathrooms: 3, score: 60 + 10 * i, commutes: { school: 10 + i, work: 20, university: null, airport: 30 - i } })))
    }
    const det = url.pathname.match(/^\/api\/listings\/(\d+)$/)
    if (det) return json({ ...detailOf(Number(det[1])), sources: [{ source: 'aqar', url: 'https://sa.aqar.fm/1', seller_phone: '0500000000', seller_name: null }],
      score_breakdown: opts.breakdown ?? null })
    if (url.pathname === '/api/map') return json([])
    if (url.pathname === '/api/places') {
      if (m === 'PUT') places = JSON.parse(route.request().postData() ?? '[]')
      return json(places)
    }
    if (url.pathname === '/api/preferences/changes') return json(changes)
    if (url.pathname === '/api/preferences') {
      if (m === 'PUT') {
        const b = JSON.parse(route.request().postData() ?? '{}')
        const hf = b.hard_filters as Record<string, number | null> | undefined
        if (hf?.price_max != null && hf.price_max < 100_000) return json({ detail: 'price_max: Input should be greater than or equal to 100000' }, 422)
        Object.assign(prefs.hard_filters, b.hard_filters)
        Object.assign(prefs.targets, b.targets)
        if (b.reset_weights) { prefs.weights = { ...WEIGHTS }; prefs.locked_weights = [] }
        for (const [k, v] of Object.entries(b.weights ?? {})) {
          prefs.weights[k] = v as number
          if (!prefs.locked_weights.includes(k)) prefs.locked_weights.push(k)
        }
        prefs.locked_weights = prefs.locked_weights.filter((k) => !(b.unlock ?? []).includes(k))
        changes.unshift({ at: new Date().toISOString(), source: 'user', explanation: 'تعديل من صفحة الإعدادات',
          diff: { 'hard_filters.price_max': { from: null, to: prefs.hard_filters.price_max } } })
      }
      return json(prefs)
    }
    if (url.pathname === '/api/adapters/aqar/resume') { adapterPaused = false; return route.fulfill({ status: 204 }) }
    if (url.pathname === '/api/status') return json({ worker: { online: true, last_seen: null, hostname: 'mac', current_job_id: null }, jobs: { pending: 0, claimed: 0, failed: 0 },
      counts: { active: 40, new: 6, bookmarked: 3, rejected: 9, passing: 25 },
      adapters: [{ source: 'aqar', status: adapterPaused ? 'paused' : 'ok', reason: adapterPaused ? 'app-version outdated' : null, last_success_at: null, last_scrape_at: new Date(Date.now() - 2 * 3600_000).toISOString() }],
      failed_jobs: [] })
    return json({}, 404)
  })
  return state
}
