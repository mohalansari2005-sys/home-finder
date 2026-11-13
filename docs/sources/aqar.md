# Aqar (sa.aqar.fm) source notes

Findings from the live probe on 2026-11-13 (single run from the Mac, paced 2-3 s).

## Transport that works
- **curl_cffi** (`impersonate="chrome"`, warm-up GET of the home page, then POST `https://sa.aqar.fm/graphql`) works and is the primary transport. No cookies are hard-coded.
- Playwright (headless and headed) got HTTP 403 on the first probe, but that run sent a stale `app-version` header, so the 403 is not conclusive. Playwright stays as the unchanged fallback.

## app-version header (important)
Aqar rejects stale clients with HTTP 200 and `{"errors":[{"message":"عذراً هذه النسخة من التطبيق قديمة، يرجى تحديث التطبيق","error":"INVALID_INPUT","code":400}]}`.
The transport maps that (message contains `قديمة` or `تحديث التطبيق`) to `AppVersionOutdated`, which pauses the adapter with the reason "aqar app-version outdated".
Current value: `1.0.3` (constant `AQAR_APP_VERSION` in `aqar_transport.py`, overridable with the env var `AQAR_APP_VERSION`).

How to find the current value when Aqar bumps it:
1. Fetch `https://sa.aqar.fm/` and collect the `https://cdn.aqar.fm/website/next/_next/static/chunks/*.js` URLs.
2. Download them and grep for `app-version`. One chunk contains `{"app-version":e.i(<module id>).version,"req-app":"web"}`.
3. Grep for `<module id>,(e,t,i)=>{t.exports={name:"aqar-next-15",version:"x.y.z"`. That `version` is the value to use.

## District filter
`where.district_id: {eq: <id>}` works with ids from the `getAllDistricts` query (`name` is like "حي النرجس", `district_id`, `count`). Match with `normalize_district`.

## Lookup by id
`where: {id: {eq: <id>}}` returned **HTTP 500** in the probe, so a by-id GraphQL lookup is NOT confirmed. `find_by_id.json` is therefore a fixture derived from the first listing of the real search response (same shape), not a captured response. The listing page `https://sa.aqar.fm` + `path` returns HTTP 200 for a live listing (removed-listing behaviour not observed). `AqarAdapter.fetch()` still tries the by-id query; revisit before Plan 3/5 rely on it (try the listing page or another where-key).

## Price filter
`price: {lte: 1500000}` is honoured server-side (20 results, max 1,495,000, min 630,000). The adapter sends it and also filters client-side.

## Image URL format
`imgs` entries are bare filenames (`000553096_1791214332889.jpg`). Real URL: `https://images.aqar.fm/webp/<W>x0/props/<filename>` (from the web client's `LISTING_IMAGES_TEMPLATE`). `640x0` verified: HTTP 200, `image/webp`. The adapter uses `640x0`.

## street_direction values
Seen in the sample: 1-8 and null. The mapping 1 north, 2 east, 3 south, 4 west, 5 northeast, 6 southeast, 7 southwest, 8 northwest, 9 three streets, 10 four streets is the plan's expectation; it was NOT cross-checked against listing pages (UNVERIFIED).

## age semantics
`age: 0` for 15 of 20 listings; only 1 of those mentions "جديد". 0 is treated as unknown (`AGE_ZERO_MEANS_NEW = False`).

## boolean semantics
`maid/driver/lift/backyard` come as `0`, `1` or `null`. Listings with `maid: 0` often mention a maid room in the text, so `0` is treated as unknown; only `1` becomes `True`.

## Other observations
- `user.phone` is the integer `0` (not exposed) in the sample; `user.name` is a real name (scrubbed in fixtures). The adapter stores `seller_phone` only for non-empty values.
- `wc` (bathrooms) and `livings` were `0` (unknown) for the first listing; zeros fail the 1-20 sanity range and become null.
- `total` for villas in Riyadh was 15391.
