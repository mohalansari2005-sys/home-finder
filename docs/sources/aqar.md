# Aqar (sa.aqar.fm) source notes

Findings from the live probe on 2026-11-13 (single run from the Mac, paced 2-3 s).

## Transport that works
- **curl_cffi** (`impersonate="chrome"`, warm-up GET of the home page, then POST `https://sa.aqar.fm/graphql`) works and is the primary transport. No cookies are hard-coded.
- Playwright (headless and headed) got HTTP 403 on the first probe, but that run sent a stale `app-version` header, so the 403 is not conclusive. Playwright stays as the unchanged fallback.

## app-version header (important)
Aqar rejects stale clients with HTTP 200 and `{"errors":[{"message":"عذراً هذه النسخة من التطبيق قديمة، يرجى تحديث التطبيق","error":"INVALID_INPUT","code":400}]}`.
The transport maps that (message contains `قديمة` or `تحديث التطبيق`) to `AppVersionOutdated`, which pauses the adapter with the reason "aqar app-version outdated".
Current value: `1.0.3` (`Settings.aqar_app_version`, set `AQAR_APP_VERSION` in `backend/.env` (Mac worker) and the server `.env`; restart the worker after changing it).

How to find the current value when Aqar bumps it:
1. Fetch `https://sa.aqar.fm/` and collect the `https://cdn.aqar.fm/website/next/_next/static/chunks/*.js` URLs.
2. Download them and grep for `app-version`. One chunk contains `{"app-version":e.i(<module id>).version,"req-app":"web"}`.
3. Grep for `<module id>,(e,t,i)=>{t.exports={name:"aqar-next-15",version:"x.y.z"`. That `version` is the value to use.

## District filter
`where.district_id: {eq: <id>}` works with ids from the `getAllDistricts` query (`name` is like "حي النرجس", `district_id`, `count`). Match with `normalize_district`.

## Lookup by id
`where: {id: {eq: N}}` fails (HTTP 500: `WhereInput` has no `id` field). The working method is `Web.listing(id: Int!)`, the query the web client uses for the listing page (found by the M3 spike on 2026-11-13):

    query getListing($id: Int!) { Web { listing(id: $id) { ...same fields as search, minus extended_details..., published } } }

- Same endpoint, headers and transport as search.
- `extended_details` is not a field of `WebListing`, so a by-id result has no villa built area (`internal_area`). Refresh therefore never overwrites known fields with None.
- **Removed** = `listing` is null with error code `"Listing not found"` (HTTP 200, `message` empty; `code` is a string here), or `published` is false (full object, price still present). Sold, expired and owner-deleted cannot be told apart.
- `last_update` changes when the platform refreshes a listing; do not use it as a change signal.
- Fixtures: `listing_by_id.json` (live capture, scrubbed, coordinates rounded to 3 decimals) and `listing_not_found.json`.
- The `/ad/<id>` web page also works but is ~260 KB and embeds an employee phone number. We never fetch or store anything from it.
- The schema is undocumented: watch for error code 414 after app-version bumps.

## Price filter
`price: {lte: 1500000}` is honoured server-side (20 results, max 1,495,000, min 630,000). The adapter sends it and also filters client-side.

## Image URL format
`imgs` entries are bare filenames (`000553096_1791214332889.jpg`). Real URL: `https://images.aqar.fm/webp/<W>x0/props/<filename>` (from the web client's `LISTING_IMAGES_TEMPLATE`). `640x0` verified: HTTP 200, `image/webp`. The adapter uses `640x0`.

## street_direction values
From the client's own dictionary (label "الواجهة"): 1 north, 2 east, **3 west, 4 south**, 5 northeast, 6 southeast, 7 southwest, 8 northwest, 9 "3 streets", 10 "4 streets". M1 had 3 and 4 swapped; fixed in M3 and cross-checked against the listing's `details` text ("الواجهة غرب" for value 3). Seller free text can still disagree with the field; the field wins.

## age semantics
`age: 0` for 15 of 20 listings; only 1 of those mentions "جديد". 0 is treated as unknown (`AGE_ZERO_MEANS_NEW = False`).

## boolean semantics
`maid/driver/lift/backyard` come as `0`, `1` or `null`. Listings with `maid: 0` often mention a maid room in the text, so `0` is treated as unknown; only `1` becomes `True`.

## Other observations
- `user.phone` is the integer `0` (not exposed) in the sample; `user.name` is a real name (scrubbed in fixtures). The adapter stores `seller_phone` only for non-empty values.
- `wc` (bathrooms) and `livings` were `0` (unknown) for the first listing; zeros fail the 1-20 sanity range and become null.
- `total` for villas in Riyadh was 15391.
