import type { Page } from '@playwright/test'

export const card = (id: number, extra: Record<string, unknown> = {}) => ({
  id, title: `فيلا ${id}`, property_type: 'villa', price: 1_500_000 + id, district: 'النرجس', bedrooms: 5, bathrooms: 4,
  built_area_m2: 400, land_area_m2: 300, photo_url: null, score: 70, commutes: { school: 10, work: 20 },
  family_status: 'new', first_seen: null, lat: 24.8, lng: 46.6, price_drop: null, status: 'active', ...extra,
})

const WEIGHTS = { commute_school: 1, commute_work: 1, commute_university: 0.6, commute_airport: 0.2, price: 1, built_area: 0.6,
  land_area: 0.4, building_age: 0.6, street_width: 0.5, facing: 0.2, street_count: 0.2, deed_type: 0.3, bedrooms: 0.4,
  bathrooms: 0.3, maid_room: 0.3, driver_room: 0.2, yard: 0.3, elevator: 0.2 }

export async function mockApi(page: Page, opts: { loggedIn?: boolean; breakdown?: unknown; paused?: boolean } = {}) {
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
  const changes: unknown[] = []
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
    if (url.pathname === '/api/feed') {
      const items = [card(1), card(2)].map((c) => ({ ...c, family_status: statuses.get(c.id) ?? c.family_status }))
        .filter((c) => c.family_status !== 'rejected')
      return json({ items, next_offset: null })
    }
    const react = url.pathname.match(/^\/api\/listings\/(\d+)\/react$/)
    if (react && m === 'POST') {
      const kind = JSON.parse(route.request().postData() ?? '{}').kind
      const st = kind === 'bookmark' ? 'bookmarked' : kind === 'reject' ? 'rejected' : 'seen'
      statuses.set(Number(react[1]), st)
      return json({ family_status: st })
    }
    const det = url.pathname.match(/^\/api\/listings\/(\d+)$/)
    if (det) return json({ ...card(Number(det[1])), description: 'وصف', livings: 2, building_age_years: null, street_width_m: 20,
      facing: 'north', street_count: 1, deed_type: null, has_maid_room: true, has_driver_room: null, has_yard: null,
      has_elevator: null, geo_precision: 'exact', photos: [], sources: [{ source: 'aqar', url: 'https://sa.aqar.fm/1', seller_phone: '0500000000', seller_name: null }],
      price_history: [], score_breakdown: opts.breakdown ?? null, status: 'active', passes_filters: true, filter_reasons: [] })
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
}
