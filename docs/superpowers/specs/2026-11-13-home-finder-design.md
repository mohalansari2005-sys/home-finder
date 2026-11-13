# Home Finder — Design Spec

**Date:** 2026-11-13
**Status:** Draft for review

## 1. Purpose

The family is searching for a home to **buy** in Saudi Arabia (Riyadh). Searching Aqar, Haraj and similar sites by hand is exhausting. Home Finder is a private web app that:

- Understands the family's needs and preferences through chat and a settings page.
- Collects listings from Aqar and Haraj, extracts structured data from them, and merges duplicates.
- Scores every listing against those preferences, with an explanation for each score.
- Shows each listing with photos, its location on a map, and rush-hour driving times to the family's fixed places.
- Learns from bookmarks, rejects (with reasons) and post-visit ratings.
- Plans in-person visit trips that group bookmarked homes by district.

**Success criteria:** the family finds and shortlists homes faster than by searching by hand, trusts the scores because they can see the reasons, and goes on visit trips the app planned.

### Users and constraints

- A single **shared family account**: one login, one set of preferences, bookmarks and feed.
- **Buying only.** No rentals.
- **Arabic first, right-to-left.** Listing content stays in its original Arabic.
- Works on **phone, iPad and desktop**, with a layout designed for each.
- Private. Not public and not multi-tenant.

### Out of scope (v1)

Rentals; multiple user profiles; push, WhatsApp or Telegram notifications; judging how a home looks from its photos; booking appointments automatically; splitting visits across several days automatically; native apps (the app is a PWA instead).

## 2. Architecture

The work is split between an always-on server and the developer's MacBook (approach A: the server holds the job queue and the Mac pulls jobs).

```
 Family (browser, Arabic RTL, PWA)
        │ HTTPS (own domain)
        ▼
┌─────────────── Hetzner VPS (1 vCPU / 2 GB / 40 GB) ─────┐
│ nginx ── static frontend (React + Vite) + TLS           │
│   └─► FastAPI backend                                   │
│        ├─ auth (single family login, session cookie)   │
│        ├─ REST: listings, feed, reactions, visits,     │
│        │        settings, worker status                │
│        ├─ chat endpoint ─► LangGraph agent (OpenAI)    │
│        └─ worker API (Tailscale interface only)        │
│ Postgres 16 + PostGIS                                  │
│ 2 GB swap file                                         │
└───────────────────────▲─────────────────────────────────┘
                        │ Tailscale (private network)
┌───────────────────────┴───── MacBook (when awake) ──────┐
│ worker (launchd service, starts on login)              │
│  ├─ scheduler (scheduled scrape every 4 h)             │
│  ├─ source adapters: aqar, haraj (API-first,           │
│  │    Playwright fallback)                             │
│  ├─ enricher: LLM extraction, geocoding, commute,      │
│  │    photos, dedupe                                   │
│  ├─ scorer / re-scorer                                 │
│  └─ learner (preference weight fitting)                │
└─────────────────────────────────────────────────────────┘
```

**Why the work is split this way:**
- The server only runs light, always-on parts. Its RAM budget is roughly Postgres 300 MB + FastAPI with LangGraph 400 MB + nginx 20 MB, plus swap. **No headless browser runs on the server.**
- The Mac does the heavy and block-prone work. Its **Saudi residential IP address** makes it far less likely to be blocked than Hetzner's datacenter IPs.
- When the Mac is offline, everything the family touches keeps working on stored data, and jobs wait in the queue.

### Tech choices

| Concern | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, LangGraph |
| LLM | OpenAI behind a thin `LLMClient` interface; a small model for bulk extraction, a stronger model for chat and agent reasoning; both set in config |
| DB | Postgres 16 + PostGIS |
| Job queue | a Postgres `jobs` table claimed with `SELECT … FOR UPDATE SKIP LOCKED` |
| Worker | Python, httpx, Playwright (only as a fallback), Pillow + imagehash |
| Frontend | React + Vite + TypeScript, Tailwind (RTL), Google Maps JS API, PWA manifest + service worker |
| Maps and routes | Google Geocoding, Routes API (rush-hour driving times, waypoint optimization) |
| Private network | Tailscale (the worker API binds to the Tailscale interface only) |
| Deploy | Docker Compose on the server; launchd plist + install script on the Mac |

## 3. Components

Each unit has one job and a narrow interface.

### 3.1 Source adapters (`worker/sources/<site>.py`)

Interface:
```python
class SourceAdapter(Protocol):
    name: str
    def search(self, query: SearchQuery) -> Iterator[RawListing]: ...
    def fetch(self, source_id: str) -> RawListing | None: ...   # None = removed
    def health(self, sample: list[RawListing]) -> HealthReport: ...
```
- **API-first:** call the internal JSON/GraphQL endpoints that the sites' own web apps use. Use Playwright only when an endpoint stops working.
- Rate limit of about 1 request every 2–3 s per site with random jitter; responses are cached by URL and hash.
- v1 sites: `aqar`, `haraj`. Adding a site = adding one module.

**Aqar specifics** (based on an existing working notebook, verified 2026-11-13):
- Endpoint: `POST https://sa.aqar.fm/graphql`, operation `findListings` (`Web.find(size, from, sort, where)`), 20 per page, filtered by `category`, `city_id`, `direction_id`, `district_id`, `published=1`. District lookup goes through `getAllCities` / `getAllDirections` / `getAllDistricts`.
- Sale categories relevant to v1 (category ids as used in the notebook): Villa_Sell=3, Apartment_Sell=6, Home_Sell=9, Floor_Sell=22. Riyadh `city_id=21`. These are confirmed against `getAllCities` when the adapter runs, not hardcoded blindly.
- Responses already contain **structured fields**: `price, area, age, beds, wc, livings, street_width, street_direction, maid, driver, lift, backyard, duplex, furnished, location{lat,lng}, imgs, content, district, direction, user{phone,name}, deed_number, ad_license_number, path, create_time, last_update`. Aqar listings therefore map straight to the canonical fields; LLM extraction only fills in fields that are null, from `content`.
- **Cloudflare blocks plain HTTP clients** (a curl request got HTTP 403 "You have been blocked"). Transport order: (1) `curl_cffi` with Chrome browser impersonation; (2) Playwright: load `sa.aqar.fm` in a real browser, then call the GraphQL endpoint from the page with `fetch`. Cookies are never hardcoded.

### 3.2 Enricher (`worker/enrich/`)

Turns a `RawListing` into a full `Listing`:
1. **LLM extraction** (needed mainly for Haraj, and for null fields on Aqar) from the Arabic title and description into typed fields (bedrooms, bathrooms, built-up area, land area, building age, street width, facing direction, number of streets, deed type, maid's/driver's room, yard, elevator, property type). Any field the text doesn't state stays `null` and is never guessed.
2. **Geocoding:** use the source's coordinates if present, otherwise geocode the district or address. Stores the accuracy (exact or district centroid).
3. **Commute:** Google Routes driving time to the 4 fixed places, departing on a weekday at 7:30 am (school, work, university) and at a typical time (airport). Results are cached by (rounded coordinates, place) in `commute_cache`.
4. **Photos:** download, convert to WebP (max 1600 px), store on the server, and compute a perceptual hash.
5. **Duplicate check:** see §5.3.

### 3.3 Scorer (`shared/scoring.py`, pure functions)

- `passes_hard_filters(listing, prefs) -> (bool, reasons)`
- `score(listing, prefs) -> ScoreResult{total: 0–100, contributions: [{factor, value, weight, delta}], missing: [factor]}`
- Each soft factor is normalized to 0–1 (for example, commute time linearly from the minutes the family is happy with to the minutes they won't accept), multiplied by its weight and summed. Missing factors are left out and listed in `missing` instead of being guessed.
- The scoring code is shared by the server (scoring a single listing at request time) and the worker (re-scoring in bulk).

### 3.4 Learner (`worker/learn.py`)

- Runs after every 10 new reactions.
- Fits an L2-regularized logistic regression on the normalized factor values. The labels: bookmark = 1, reject = 0; visit rating 4–5 = 1 with sample weight 3; visit rating 1–2 = 0 with sample weight 3.
- Blends the result into the current weights: `w_new = w + 0.3·(w_fit − w)`, with each weight's change capped at ±20% per update. Weights the user set by hand are **locked** and never auto-adjusted.
- Writes a human-readable entry to `preference_changes` (for example, "increased street-width importance based on rejections"). It appears in Settings and the agent can mention it.
- Reject reasons: the quick reasons (`too_old`, `narrow_street`, `bad_layout`, `overpriced`, `far`, `other`) plus free text. When the same reason keeps coming up (≥5 times in the last 20 rejects), the agent suggests turning it into a hard filter. The family must confirm it.

### 3.5 LangGraph agent (`server/agent/`)

The agent replies in Arabic. Its tools:
- `get_preferences`, `update_preferences(patch)`. Every change is shown to the family as a short confirmation.
- `search_listings(filters, sort, limit)`, which searches the local database.
- `get_listing(id)` and `compare_listings(ids)`.
- `request_scrape(query)`, which queues an on-demand job. If the Mac has been offline for more than 10 minutes, it falls back to a single small API search run on the server (Aqar only, `curl_cffi`, no browser, at most 1 page). If that is blocked too, the agent tells the family that results will arrive once the Mac is back online.
- `suggest_visit_trip(district_group)`.

Conversation state is persisted with a LangGraph Postgres checkpointer. Chat replies stream to the browser over SSE.

### 3.6 Job queue

The `jobs` table holds: `id, type, payload jsonb, status (pending|claimed|done|failed), attempts, claimed_at, error, created_at`.
- Job types: `scrape_search`, `refresh_listing`, `enrich_listing`, `rescore_all`, `learn`, `precheck_trip`.
- The worker API (Tailscale only, protected by a shared token) has three endpoints: `POST /worker/claim?types=…&n=…`, `POST /worker/complete/{id}`, `POST /worker/fail/{id}`. The worker also writes results directly to Postgres over Tailscale.
- If a claimed job isn't finished within 15 minutes, it goes back to `pending`. Failed jobs are retried up to 3 times with growing delays (1 min, 10 min, 1 h), then marked `failed`.
- The worker sends a heartbeat every minute to `worker_status`, which the Settings screen shows.

### 3.7 Frontend (`web/`)

Responsive React PWA in Arabic, right-to-left. Breakpoints: phone < 768 px, iPad 768–1199 px, desktop ≥ 1200 px.

| | Phone | iPad | Desktop |
|---|---|---|---|
| Navigation | bottom tab bar | collapsible side menu (right) | fixed side menu (right) |
| Feed | one column of cards | two columns, or list + detail in landscape | feed list + map side by side, linked highlight |
| Map | full screen + swipe-up card sheet | map + panel in landscape | combined with feed |
| Chat | full-screen tab | slide-over panel | docked panel |
| Listing detail | full-screen page | side panel | side panel or wide modal |
| Compare | swipe between 2 | 2–3 side by side | table of up to 4 |

**Screens:** Feed · Map · Listing detail · Assistant · Visits · Settings.
- **Feed card:** main photo, price (with a price-drop badge), district, score badge, commute chips for the 4 places, bookmark and reject buttons. Filters: new since last visit, bookmarked, district.
- **Map:** Google Maps in Arabic; pins colored by score; separate markers for the 4 fixed places; bookmarked listings styled differently.
- **Detail:** photo gallery; all fields with the missing ones highlighted; top 3 pluses and minuses plus the full score breakdown; commute times with a route link; links to the source site(s); call and WhatsApp buttons for the seller; family notes.
- **Settings:** the 4 fixed places (picked on a map); hard filters; weight sliders (moving one locks it); preference-change history; password; worker status (Mac last seen, pending and failed jobs, adapter health).
- **Desktop shortcuts:** B to bookmark, X to reject, ←/→ for next and previous.
- **Touch:** no action is hover-only.

Listing status: `new → seen → bookmarked | rejected → visited`. Rejected listings are hidden, with an undo option.

### 3.8 Visit planner (`server/visits/`)

1. **Groups:** bookmarked listings are grouped by district; neighboring districts are merged when the drive between their centroids is ≤ 10 min. Each group shows its count and average score.
2. **Building a trip:** the family picks a group (or the agent suggests one), then a date, start time, starting point (home or any fixed place) and minutes per visit (default 30).
3. **Ordering:** Google Routes waypoint optimization produces a timeline with arrival and departure times.
4. **Arranging visits:** each stop has a WhatsApp button with a pre-filled Arabic message that includes the proposed time. Stop status: `not_contacted → contacted → confirmed → visited | cancelled`. Cancelling a stop re-optimizes the rest of the trip.
5. **Before the trip:** a `precheck_trip` job re-fetches every listing in the trip and flags any that were removed or had a price change.
6. **Open in Google Maps:** a multi-stop route link.
7. **After the visit:** a 1–5 rating, notes and photos for each stop, which feed the learner (§3.4).

## 4. Data model (core tables)

- `listings`: id, canonical fields (price, property_type, district, city, bedrooms, bathrooms, built_area_m2, land_area_m2, building_age_years, street_width_m, facing, street_count, deed_type, has_maid_room, has_driver_room, has_yard, has_elevator, …), `geom geography(Point)`, geo_precision, status (`active|removed`), first_seen, last_seen, score, score_breakdown jsonb, family_status (`new|seen|bookmarked|rejected|visited`).
- `listing_sources`: listing_id, source, source_id, url, raw jsonb, seller_phone, fetched_at. One listing can have several sources after duplicates are merged.
- `listing_price_history`: listing_id, price, observed_at.
- `photos`: listing_id, path, phash, position.
- `places`: the 4 fixed places (school, work, university, airport): name, kind, geom.
- `commute_cache`: rounded origin, place_id, minutes, computed_at.
- `preferences`: a single row with hard_filters jsonb, weights jsonb, locked_weights text[].
- `preference_changes`: at, source (`user|learner|agent`), diff jsonb, explanation.
- `reactions`: listing_id, kind (`bookmark|reject|unreject|visit_rating`), reason_code, note, rating, at.
- `notes`: listing_id, text, at.
- `visit_trips`, `visit_stops`: trip date, start, origin, timeline; each stop has listing_id, order, eta, status, rating, notes.
- `jobs`, `worker_status`, `adapter_health`.
- LangGraph checkpoint tables.

## 5. Data flow

### 5.1 Scheduled refresh
Every 4 h the scheduler queues `scrape_search` jobs built from the hard filters. Each new listing gets an `enrich_listing` job. Each listing already stored gets its price and status updated and its price history recorded. Then it's scored and shown in the feed as `new`.

### 5.2 Chat-driven search
The family asks in chat, and the agent updates preferences if needed and searches the database. If there are too few results, it calls `request_scrape`, tells the family "searching, results will appear in the feed," and new listings stream into the feed as they're enriched.

### 5.3 Duplicate merging
Two listings are duplicates if they are within 50 m of each other, their built-up area and land area are within 5%, their price is within 3%, **and** at least one pair of photos has a perceptual-hash distance ≤ 8. Without photos, all three numeric checks must hold and the property type must match. Merged listings keep every source in `listing_sources`.

### 5.4 Learning
A reaction is saved. On every 10th one, a `learn` job runs on the Mac and updates the weights, a `preference_changes` entry is recorded, and a `rescore_all` job is queued.

## 6. Failure handling

- **Adapter health:** after each batch, the share of results missing a price, location or area is compared with a baseline. If more than 50% are missing, that adapter is paused, `adapter_health` records it, and Settings shows an alert. Nothing from that batch is published.
- **Blocking (HTTP 403/429 or a captcha):** back off exponentially, try the Playwright fallback once, then pause the adapter.
- **Jobs:** retries and reclaiming stale jobs as described in §3.6. Failed jobs are shown in Settings with their error.
- **Mac offline:** the Settings screen shows the time since the last heartbeat; the agent mentions it when a search depends on fresh data.
- **External APIs (OpenAI, Google):** the listing is saved with whatever data is available and an `enrich_listing` job is re-queued. Spending is tracked monthly in a `api_usage` table with a hard cap per provider in config; once the cap is reached, calls stop and Settings shows a warning.
- **Data quality:** extracted values outside sanity ranges (for example, price < 100k SAR, area < 50 m², age > 80 yrs) are set to `null` and logged.

## 7. Deployment and operations

- **Server:** Docker Compose with `db` (postgis/postgis:16), `api` (FastAPI + Uvicorn, 1 worker) and `nginx` (static frontend + reverse proxy + Let's Encrypt via certbot). Postgres is tuned for low memory (`shared_buffers=128MB`). A 2 GB swap file. Tailscale is installed on the host.
- **Mac:** `scripts/install-worker.sh` sets up a Python venv, Playwright Chromium, Tailscale check, and `~/Library/LaunchAgents/com.homefinder.worker.plist`. Logs go to `~/Library/Logs/homefinder/`.
- **Deploy:** `scripts/deploy.sh` runs `git pull`, builds the frontend, then `docker compose up -d --build` and Alembic migrations.
- **Backups:** a nightly `pg_dump`, compressed, keeping the last 14, copied to Hetzner Storage Box (or the Mac over Tailscale if no Storage Box is set up). Photos are backed up weekly.
- **Secrets:** a `.env` file on each machine (OpenAI key, Google key, family password hash, worker token, DB URL). Nothing is committed to git.

## 8. Testing

- **Adapters:** fixture-based tests on saved real responses from Aqar and Haraj (`tests/fixtures/<site>/`). No live requests in CI.
- **Pure logic:** unit tests for scoring, hard filters, normalization, the learner (on synthetic reactions, weights move in the expected direction and stay within caps), duplicate detection, district grouping and trip ordering (with the Routes client mocked).
- **Extraction:** about 30 labeled Arabic listing texts, checking field-level accuracy against the expected values; run by hand when the prompt or model changes.
- **Agent:** about 15 scripted Arabic conversations, checking which tools are called and the resulting preference changes (LLM recorded or mocked for CI).
- **API:** pytest + httpx against a test Postgres+PostGIS container.
- **End-to-end:** Playwright tests of login → feed → bookmark/reject → detail → build trip, at phone, iPad and desktop screen sizes, in RTL.

## 9. Milestones

1. **First usable version:** DB schema, job queue, Mac worker, Aqar adapter, enrichment (extraction, geocoding, commute, photos), basic feed + map, login, deployment to the domain.
2. Scoring with explanations, full listing detail, settings (places, filters, weights), worker status.
3. LangGraph chat agent, Haraj adapter, duplicate merging, price history.
4. Learning from reactions and reject reasons, preference-change history, comparison view.
5. Visit planner (groups, trips, WhatsApp messages, pre-trip check, post-visit ratings).

## 10. Cost estimate (monthly)

- Hetzner VPS: current plan.
- OpenAI: about $5–15 (bulk extraction on the small model; chat on the stronger model).
- Google Maps Platform: expected to be within the monthly free credit, since commute times are cached per listing and place. Needs a billing account.
- Tailscale: free plan.

## 11. Risks

- **Scraping fragility and site terms:** Aqar and Haraj have no public API, and their internal endpoints can change or be blocked without notice. Mitigations: one adapter per site, fixture tests, health checks, a residential IP, low request rates, and personal non-commercial use only.
- **2 GB server:** tight but workable because nothing heavy runs there. If memory gets tight, the first step is moving to a 4 GB plan.
- **Mac availability:** data only refreshes while the Mac is awake. This is acceptable for a family search measured in weeks.
