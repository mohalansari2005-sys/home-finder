# Haraj (haraj.com.sa) source notes

Findings from the live discovery on 2026-11-13: about 25 read-only requests, 2.5 s apart, no login, no block or challenge seen.

## How the data is served
haraj.com.sa is a React Router app. Tag pages are server-rendered (the posts are in the streamed loader data), and the
client then pages through the public GraphQL endpoint:

- `POST https://graphql.haraj.com.sa/?queryName=posts&clientId=<random 16 hex>&version=<build stamp>`
- headers: `Content-Type: application/json`, `origin`/`referer` of haraj.com.sa. No cookies and no token are needed.
- body: `{"query": <FetchAds>, "variables": {...}}` (the `FetchAds` query found in the site's JS bundle).
- `clientId` can be any random string and `version` any build-like string (probe).

The site's bundle also contains a server-to-server header (`BETWEEN-SERVERS-KEY`) for its own SSR. **We do not use it.**
Only the unauthenticated browser request is replayed.

### Search
variables `{"tag": "فلل للبيع", "city": "الرياض", "page": N}`.
- Pages are 1-based: `page` 0 and 1 return the same results. Our `search(tag, city, page)` is 0-based and sends `page + 1`.
- About 20 posts per page (16 to 21 seen: some are filtered out after paging). `pageInfo.hasNextPage` says whether more exist.
- Results are newest first. Posts in the same tag from other cities (الخرج, المزاحمية) can still appear under `city: "الرياض"`;
  filter on `city` in the adapter.
- Response path: `data.posts.items[]`.

### Post detail
The search response already holds the full body text and all images, so no separate detail call is needed for ingest.
For a single post (used by the stale-listing refresh): variables `{"id": [<post id>]}` returns that one item.
An unknown id returns an empty `items`. Old posts remain queryable by id (a 2022 post still returned), so "removed" cannot
be inferred from age. Posts whose `status` is false, or that no longer carry a sale tag, are treated as removed.

## Fields (our slim query asks only for these)
| Need | Field |
|---|---|
| id | `id` (int); the post URL is `https://haraj.com.sa/` + `URL` (`11<id>/<slug>/`), we use `https://haraj.com.sa/<id>` |
| title | `title` |
| body | `bodyTEXT` (plain text; contains HTML entities such as `&ndash;`) |
| price | `price { formattedPrice inputPrice }` is **null on every real-estate post seen (40 of 40)**. Price lives in the body (licensed posts carry `سعر الوحدة: 1600000`; others say "السعر: 4,800,000 ريال"). `parse_price_from_text` (`haraj_text.py`) reads it deterministically after `السعر`, `سعر الوحدة`, `المطلوب` or `الحد` (100,000 to 50,000,000 SAR); the LLM step fills only what is left. |
| city | `city`, `geoCity` |
| district | `geoNeighborhood` (always present, 40 of 40), also in tags as `فلل للبيع في حي X في الرياض` |
| geo | `geoHash` (9 char geohash, about 5 m). It matches the Google-Maps link in the body when both exist. Used as `approximate` coordinates. A Google Maps link with coordinates in the body wins over it (`parse_maps_link`); if the two are more than 2 km apart the adapter logs a warning and lowers `geo_precision` one level (`district`), which also keeps the post out of dedupe. |
| images | `imagesList` (full URLs, `mimg6cdn.haraj.com.sa` / `img4cdn.haraj.com.sa`), `thumbURL` is a bare filename |
| date | `postDate`, `updateDate` (unix seconds) |
| tags | `tags` |
| seller | `authorUsername`, `authorId`: **never requested.** `realEstateInfo` (REGA licence numbers) is never requested either. |
| phone | Not exposed by the API at all. The page shows it after a "contact" click. Bodies sometimes contain a phone or the site's own mask text `( رقم الجوال يظهر عند الضغط على زر تواصل )`. We store `seller_phone = None`. |

Body conventions seen: licensed posts end with a regulated block `معلومات العقار حسب الرخصة` (purpose, unit price, type, age,
area, facing, rooms, plan and plot numbers, street width) and a Google Maps link `https://maps.google.com/?q=lat,lng`
(37 of 40 posts).

## Tags for sale categories (verified by query)
| Property type | Tag |
|---|---|
| villa | `فلل للبيع` |
| apartment | `شقق للبيع` |
| floor | `دور للبيع` (`أدوار للبيع` returns nothing) |
| house | `بيوت للبيع` |

Tag results are noisy: "wanted" posts (`مطلوب ...`, `ابحث عن ...`), rent posts mislabeled as sale (`للإيجار`), and
posts of another type (a villa under `بيوت للبيع`). The adapter skips rent and wanted posts, and takes the property type from the tags.

## Transport
`curl_cffi` (`impersonate="chrome"`, warm-up GET of the home page, then the POST) works and is primary.
A Playwright fallback (`page.evaluate(fetch)` from a loaded haraj.com.sa page) is implemented in `haraj_transport.py`
but was not exercised live. Any non-200, non-JSON or GraphQL `errors` response raises `Blocked`.

## Not verified
- What a deleted/expired post looks like by id (the probe only saw empty results for ids that never existed).
- Rate-limit thresholds: nothing seen at about 25 requests.
- Whether `tag` + `city: "الرياض"` is complete: we did not compare against the site's own paging past page 3.
