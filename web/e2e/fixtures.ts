import type { Page } from '@playwright/test'

export const card = (id: number, extra: Record<string, unknown> = {}) => ({
  id, title: `فيلا ${id}`, property_type: 'villa', price: 1_500_000 + id, district: 'النرجس', bedrooms: 5, bathrooms: 4,
  built_area_m2: 400, land_area_m2: 300, photo_url: null, score: 70, commutes: { school: 10, work: 20 },
  family_status: 'new', first_seen: null, lat: 24.8, lng: 46.6, price_drop: null, ...extra,
})

export async function mockApi(page: Page, opts: { loggedIn?: boolean } = {}) {
  let loggedIn = opts.loggedIn ?? false
  const statuses = new Map<number, string>()
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
      price_history: [], score_breakdown: null, status: 'active' })
    if (url.pathname === '/api/map') return json([])
    if (url.pathname === '/api/places') return json([])
    if (url.pathname === '/api/status') return json({ worker: { online: true, last_seen: null, hostname: 'mac', current_job_id: null }, jobs: { pending: 0, claimed: 0, failed: 0 }, adapters: [], failed_jobs: [] })
    return json({}, 404)
  })
}
