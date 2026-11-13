# Plan 3 — Haraj Adapter, Dedupe, Price Drops, Chat Agent

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Haraj listings flow in alongside Aqar, and the same house listed on both is merged into one card. Price drops are badged. The family can chat in Arabic with a LangGraph agent that edits preferences, searches stored listings, compares them, and starts new searches.

**Architecture:** The Haraj adapter follows the Aqar pattern (transport → parse → `RawListing`), with its own health rule because Haraj posts often lack a price. Dedupe runs at the end of `enrich_listing` (after photos, so phashes exist). The agent runs **on the server**: a LangChain v1 `create_agent` graph with a Postgres checkpointer and tools bound to DB sessions, streamed to the browser over SSE.

**Tech Stack:** Adds to the server extra: `langchain>=1.0`, `langchain-openai>=1.0`, `langgraph>=1.0`, `langgraph-checkpoint-postgres>=2.0`, `psycopg-pool>=3.2`, `curl_cffi>=0.7`.

**Spec:** `docs/superpowers/specs/2026-11-13-home-finder-design.md` §3.1 (Haraj), §3.5, §5.2, §5.3, §3.7 (Assistant), §6

## Global Constraints

All constraints in `2026-11-13-00-overview.md`. Plans 1–2 must be complete and green. After adding the agent dependencies, rebuild `deploy/api.Dockerfile` locally and confirm the api container idles at **< 450 MiB** (`docker stats`). If it's over, report `NEEDS_ADVICE`.

## Review Focus

1. **Two different houses next door with the same price** (≤ 50 m apart, same price, but areas differ by > 5%) must **not** merge. Pinned in `test_neighbors_not_merged`.
2. **A Haraj post with no price, no area and no coordinates** still ingests. The Haraj health check doesn't pause the adapter just because prices are missing. Pinned in `test_haraj_health_tolerates_missing_price`.
3. **The chat request arrives when the OpenAI monthly cap is reached:** the stream sends an `error` event with an Arabic message, and no model call is made. Pinned in `test_chat_budget_exceeded`.
4. **The agent receives an invalid preference value** (for example `price_max: 5`): the tool returns a readable error to the model and preferences stay unchanged. Pinned in `test_update_preferences_tool_rejects_invalid`.
5. **The browser disconnects mid-stream:** the server stops generating without an unhandled exception, and the conversation state up to the last completed step is kept. Pinned in `test_chat_client_disconnect`.

---

### Task 1: Haraj discovery, transport, fixtures

This is a live task. Do one discovery session with pacing. If Haraj's data can't be obtained with either transport, report `NEEDS_ADVICE`.

**Files:**
- Create: `backend/scripts/haraj_probe.py`, `backend/homefinder/worker/sources/haraj_transport.py`, `backend/tests/fixtures/haraj/search_villas_riyadh.json`, `backend/tests/fixtures/haraj/post_detail.json`, `docs/sources/haraj.md`

**Interfaces:**
- Produces: `HarajTransport` with `search(tag: str, city: str, page: int) -> dict` and `post(post_id: str) -> dict | None`, raising `Blocked` (reuse the class from `aqar_transport`). Also `make_haraj_transport()`.

- [ ] **Step 1: Discover the endpoints with Playwright network capture**

`backend/scripts/haraj_probe.py`:
```python
"""Load Haraj real-estate pages in a real browser and log the JSON/GraphQL XHRs the site makes.
Output: tests/fixtures/haraj/raw/*.json (gitignored) + printed endpoint summary."""
import json
import random
import time
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

RAW = Path(__file__).parents[1] / "tests" / "fixtures" / "haraj" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
PAGES = [
    "https://haraj.com.sa/tags/" + quote("فلل للبيع") + "?city=" + quote("الرياض"),
    "https://haraj.com.sa/tags/" + quote("الرياض") + "/" + quote("فلل للبيع"),
]
captured = []

with sync_playwright() as pw:
    b = pw.chromium.launch(headless=False)
    page = b.new_page(locale="ar-SA")

    def on_response(r):
        ct = r.headers.get("content-type", "")
        if "json" in ct and r.request.resource_type in ("xhr", "fetch"):
            try:
                body = r.json()
            except Exception:
                return
            i = len(captured)
            captured.append({"url": r.url, "method": r.request.method, "post": r.request.post_data, "status": r.status})
            (RAW / f"resp_{i}.json").write_text(json.dumps(body, ensure_ascii=False, indent=1), "utf-8")

    page.on("response", on_response)
    for url in PAGES:
        page.goto(url, wait_until="networkidle", timeout=60_000)
        time.sleep(random.uniform(2, 3))
        page.mouse.wheel(0, 4000)
        time.sleep(random.uniform(2, 3))
    first_post = page.locator("a[href*='/1']").first  # post links look like /11xxxxxxx/...
    if first_post.count():
        first_post.click()
        page.wait_for_load_state("networkidle")
        time.sleep(2)
    b.close()

(RAW / "index.json").write_text(json.dumps(captured, ensure_ascii=False, indent=1), "utf-8")
for c in captured:
    print(c["status"], c["method"], c["url"][:140], (c["post"] or "")[:200])
```
Run: `.venv/bin/python scripts/haraj_probe.py`. If the tag URL pattern 404s, open haraj.com.sa by hand in the headed browser, navigate to العقارات → فلل للبيع → الرياض (Real estate → Villas for sale → Riyadh), and rerun with the URL you landed on.

- [ ] **Step 2: Record findings** in `docs/sources/haraj.md`:
  - The search endpoint: URL, method, request body/query (GraphQL operation name and variables if GraphQL), how the tag and city are passed, page size and paging.
  - The post-detail endpoint, or whether the search response already includes the full body text and images.
  - The field names for: id, title, body/text, price (if any), city, district/neighborhood (if any), geo (if any), images, post URL, author phone (often hidden; record whether a contact number appears at all), date, and tags.
  - The exact tag strings for sale categories: villas, apartments, floors, houses (فلل للبيع, شقق للبيع, أدوار للبيع, بيوت للبيع, or whatever the site actually uses).
  - Which transport works: `curl_cffi` replaying the request, or Playwright `page.evaluate(fetch)` as in the Aqar transport.

- [ ] **Step 3: Implement `haraj_transport.py`** using the confirmed endpoint(s). Mirror `aqar_transport.py`: a `CurlCffiHaraj` (warm up by GET-ing the home page, then replay the request with browser impersonation), a `PlaywrightHaraj` (`page.evaluate` fetch from a loaded haraj.com.sa page), and a `FallbackTransport` from aqar_transport reused generically. The interface is `search(tag, city, page) -> dict` and `post(post_id) -> dict | None`. Any non-200 or non-JSON response raises `Blocked`.

- [ ] **Step 4: Scrub + commit fixtures**
```bash
.venv/bin/python ../scripts/scrub_fixture.py tests/fixtures/haraj/raw/<search resp>.json tests/fixtures/haraj/search_villas_riyadh.json
.venv/bin/python ../scripts/scrub_fixture.py tests/fixtures/haraj/raw/<post resp>.json tests/fixtures/haraj/post_detail.json
.venv/bin/pytest tests/test_fixtures_scrubbed.py -v
```
If Haraj uses other key names for author data (for example `authorUsername`), add them to `scrub_fixture.py` (`PHONE_KEYS`, a name-like key set) with a test case in `test_scrub.py` **before** scrubbing.

- [ ] **Step 5: Commit**
```bash
git add backend/scripts/haraj_probe.py backend/homefinder/worker/sources/haraj_transport.py backend/tests/fixtures/haraj/*.json docs/sources/haraj.md scripts backend/tests/test_scrub.py
git commit -m "feat: haraj endpoint discovery, transport and scrubbed fixtures"
```

---

### Task 2: Haraj adapter

**Files:**
- Create: `backend/homefinder/worker/sources/haraj.py`, `backend/tests/worker/test_haraj.py`
- Modify: `backend/homefinder/worker/main.py` (register `"haraj"` adapter), `backend/homefinder/worker/scheduler.py` (`ENABLED_SOURCES = ["aqar", "haraj"]`)

**Interfaces:**
- Consumes: `HarajTransport`, `RawListing`, `Pacer`, `sanity`, `textnorm`.
- Produces:
  - `HARAJ_TAG_BY_TYPE: dict[PropertyType, str]` (from docs/sources/haraj.md)
  - `parse_post(d: dict) -> RawListing | None` (returns None for rent posts or non-real-estate posts)
  - `HarajAdapter(transport, pacer=None)` implementing `SourceAdapter`, where `health()` = the share of posts missing a title **or** body > 50% with ≥ 10 samples (price is not checked).

- [ ] **Step 1: Failing tests**

`backend/tests/worker/test_haraj.py`:
```python
import json
from pathlib import Path

from homefinder.schemas import SearchQuery
from homefinder.worker.sources.base import Pacer
from homefinder.worker.sources.haraj import HarajAdapter, parse_post

FX = Path(__file__).parents[1] / "fixtures" / "haraj"


def posts():
    """Return the list of post dicts inside the scrubbed search fixture (path per docs/sources/haraj.md)."""
    from homefinder.worker.sources.haraj import extract_posts
    return extract_posts(json.loads((FX / "search_villas_riyadh.json").read_text("utf-8")))


def test_parse_real_post():
    r = parse_post(posts()[0])
    assert r.source == "haraj" and r.url.startswith("https://haraj.com.sa/")
    assert r.fields.description and r.fields.city
    assert r.fields.property_type == "villa"


def test_parse_minimal_post():
    r = parse_post({"id": 1, "title": "فيلا للبيع حي الملقا", "bodyTEXT": "فيلا دورين", "city": "الرياض", "tags": ["فلل للبيع"]},
                   field_map_override=True)
    assert r is not None and r.fields.price is None and r.fields.lat is None and r.photo_urls == []


def test_rent_posts_skipped():
    assert parse_post({"id": 2, "title": "فيلا للإيجار", "tags": ["فلل للإيجار"], "city": "الرياض"}, field_map_override=True) is None


def test_haraj_health_tolerates_missing_price():
    rs = [parse_post({"id": i, "title": "فيلا", "bodyTEXT": "نص", "city": "الرياض", "tags": ["فلل للبيع"]}, field_map_override=True)
          for i in range(20)]
    assert HarajAdapter(transport=None, pacer=Pacer(sleep=lambda s: None)).health(rs).ok


def test_search_paginates_and_stops():
    class T:
        def __init__(self): self.calls = []
        def search(self, tag, city, page):
            self.calls.append(page)
            from homefinder.worker.sources.haraj import wrap_posts_for_test
            return wrap_posts_for_test(posts() if page == 0 else [])
        def close(self): pass
    t = T()
    out = list(HarajAdapter(t, pacer=Pacer(sleep=lambda s: None)).search(SearchQuery(property_types=["villa"], max_pages=5)))
    assert t.calls == [0, 1] and len(out) >= 1
```
`field_map_override=True` means "the dict already uses the canonical test keys (`id, title, bodyTEXT, city, tags, price, imagesList, geo`)". Implement `parse_post` so that one `_FIELD_MAP` dict maps canonical names to the real Haraj keys recorded in docs/sources/haraj.md. With `field_map_override=True`, the identity map is used. `extract_posts(resp)` and `wrap_posts_for_test(list)` encode where posts live in the search response.

- [ ] **Step 2: Implement haraj.py**

Required behavior:
- **Property type:** from the tags via `HARAJ_TAG_BY_TYPE`. If no sale tag matches, return `None`. If any tag or the title contains "إيجار" or "للإيجار", return `None`.
- **District:** if the API provides one, use it. Otherwise regex `حي\s+([؀-ۿ]+(?:\s[؀-ۿ]+)?)` on the title, then the body. Normalize with `normalize_ar`.
- **Price:** from the API field if present (`clean_int(..., *PRICE)`), else `None`. The LLM extraction in enrich fills it in from the body.
- **Coordinates:** use API geo only if present and inside Saudi bounds; `geo_precision="approximate"`.
- **photo_urls:** full image URLs. **url:** `https://haraj.com.sa/<id>` (or the path the API gives).
- **seller_phone:** only if the API exposes it; never scraped from hidden fields.
- **search():** for each property type → tag; page 0.. `max_pages-1` (if `q.districts` is set, `max_pages` from `SearchQuery` is still 5); stop on an empty page; `price_max` filter as in Aqar (only when price is known).
- **fetch(source_id):** `transport.post(id)` → `parse_post` or `None`.

- [ ] **Step 3: Register.** In `main.build_deps`: `"haraj": lambda: HarajAdapter(make_haraj_transport())`. In the scheduler, set `ENABLED_SOURCES = ["aqar", "haraj"]`. Update `test_scheduler.py` to expect 2 jobs, and Plan 2's `test_search_relevant_change_enqueues_scrape` to expect one `scrape_search` per source (2).

- [ ] **Step 4: Extraction accuracy set (spec §8)**

Create `backend/tests/fixtures/extraction/cases.yaml` with **30** labeled cases: 15 taken from the `content` of scrubbed Aqar fixtures, 15 from scrubbed Haraj post bodies. Each case is `{text: "...", expected: {field: value, ...}}` and lists only the fields the text states explicitly. Also add `backend/tests/test_extraction_llm.py` (`@pytest.mark.llm`). It runs `extract_missing(make_llm(), Listing(description=text))` for each case and computes field-level precision (extracted values that match expected) and recall (expected values that were extracted). It prints a table and asserts precision ≥ 0.9. Run manually with a real key and put the numbers in the commit message.

- [ ] **Step 5: Run backend suite — expect PASS.** Commit:
```bash
git add backend
git commit -m "feat: haraj adapter with sale-only parsing, district extraction and tolerant health check"
```

---

### Task 2b: Mark disappeared listings as removed (spec §5.1)

**Files:**
- Modify: `backend/homefinder/worker/scheduler.py`, `backend/homefinder/worker/handlers.py`, `backend/homefinder/server/routes/listings.py`, `web/src/components/ListingCard.tsx`
- Create: `backend/tests/worker/test_refresh.py`

**Interfaces:**
- `scheduler.enqueue_stale_refreshes(s, older_than=timedelta(days=3), limit=30) -> int`, called from `maybe_schedule` when the scrape is scheduled. For active, non-merged listings with `last_seen < now - older_than`, it enqueues `refresh_listing` `{"listing_id"}` with dedupe `refresh:<id>`, oldest first, at most `limit`.
- Handler `refresh_listing`: takes the first source → `adapter.fetch(source_id)`. `None` → `listing.status = "removed"`. A `RawListing` → `ingest_raw` (updates `last_seen`, price). The adapter is paused → `{"skipped": "paused"}`.
- The feed already hides `status = "removed"` from the all/new views. The bookmarked view still shows them, and the card shows a grey "الإعلان محذوف" (listing removed) chip when the card's `status == "removed"`. Add `status` to `card()`.

- [ ] **Step 1: Failing test** `test_refresh.py`: one listing with `last_seen` 4 days ago and an adapter whose `fetch` returns `None` → after `maybe_schedule` + `dispatch("refresh_listing")` the listing is `removed`. A listing seen 1 day ago isn't enqueued. A fetch that returns a newer price updates it and records history.
- [ ] **Step 2: Implement; run the suite; commit** `feat: refresh stale listings and mark removed ones`.

---

### Task 3: Duplicate detection and merge

**Files:**
- Create: `backend/homefinder/dedupe.py`, `backend/tests/test_dedupe.py`
- Modify: `backend/homefinder/worker/enrich/pipeline.py` (after photos: `dedupe_and_merge`)

**Interfaces:**
- Produces:
  - `dedupe.is_duplicate(a: Listing, b: Listing, a_hashes: list[str], b_hashes: list[str]) -> bool`
  - `dedupe.find_duplicate(s, listing) -> Listing | None` (searches candidates within 50 m with `geo_precision in ('exact','approximate')`, active, not merged, different id)
  - `dedupe.merge(s, keep: Listing, dup: Listing) -> None`
  - `dedupe.dedupe_and_merge(s, listing_id) -> int | None` (returns the id of the surviving listing when a merge happened)

- [ ] **Step 1: Failing tests**

`backend/tests/test_dedupe.py`:
```python
from geoalchemy2.elements import WKTElement

from homefinder.dedupe import dedupe_and_merge, is_duplicate
from homefinder.models import Listing, ListingSource, Photo, PriceHistory, Reaction

H1 = "f0e0d0c0b0a09080"
H1_NEAR = "f0e0d0c0b0a09081"  # hamming 1
H_FAR = "0f1f2f3f4f5f6f7f"


def mk(db, lat=24.8, lng=46.6, price=2_000_000, built=400, land=300, ptype="villa", phashes=(), src="aqar", sid="1", **kw):
    l = Listing(lat=lat, lng=lng, geom=WKTElement(f"POINT({lng} {lat})", srid=4326), geo_precision="exact",
                price=price, built_area_m2=built, land_area_m2=land, property_type=ptype, **kw)
    db.add(l); db.flush()
    db.add(ListingSource(listing_id=l.id, source=src, source_id=sid, url=f"https://{src}/{sid}", raw={}))
    for i, h in enumerate(phashes):
        db.add(Photo(listing_id=l.id, position=i, path=f"{l.id}/{i}.webp", phash=h))
    db.add(PriceHistory(listing_id=l.id, price=price))
    db.flush()
    return l


def test_is_duplicate_rules():
    a = Listing(price=2_000_000, built_area_m2=400, land_area_m2=300, property_type="villa")
    b = Listing(price=2_040_000, built_area_m2=410, land_area_m2=300, property_type="villa")
    assert is_duplicate(a, b, [H1], [H1_NEAR])
    assert not is_duplicate(a, b, [H1], [H_FAR])                       # photos disagree
    assert is_duplicate(a, b, [], [])                                  # no photos: numbers + type suffice
    assert not is_duplicate(a, Listing(price=2_200_000, built_area_m2=400, land_area_m2=300, property_type="villa"), [], [])
    assert not is_duplicate(a, Listing(price=2_000_000, built_area_m2=400, land_area_m2=300, property_type="apartment"), [], [])
    assert not is_duplicate(Listing(price=2_000_000), Listing(price=2_000_000), [], [])  # no comparable area


def test_merge_keeps_older_and_moves_everything(db):
    old = mk(db, phashes=[H1], sid="a1", bedrooms=None)
    new = mk(db, lat=24.80020, phashes=[H1_NEAR], src="haraj", sid="h9", bedrooms=5, family_status="bookmarked")
    db.add(Reaction(listing_id=new.id, kind="bookmark")); db.commit()
    assert dedupe_and_merge(db, new.id) == old.id
    db.commit(); db.expire_all()
    old, new = db.get(Listing, old.id), db.get(Listing, new.id)
    assert new.merged_into_id == old.id
    assert {s.source for s in db.query(ListingSource).filter_by(listing_id=old.id)} == {"aqar", "haraj"}
    assert old.bedrooms == 5 and old.family_status == "bookmarked"
    assert db.query(Reaction).filter_by(listing_id=old.id).count() == 1


def test_neighbors_not_merged(db):
    a = mk(db, sid="a", built=400, land=300)
    b = mk(db, lat=24.80030, sid="b", built=450, land=360)  # ~33 m away, same price, areas differ >5%
    db.commit()
    assert dedupe_and_merge(db, b.id) is None


def test_far_apart_not_candidates(db):
    mk(db, sid="a"); b = mk(db, lat=24.81, sid="b"); db.commit()  # ~1.1 km
    assert dedupe_and_merge(db, b.id) is None
```

- [ ] **Step 2: Implement dedupe.py**

```python
import imagehash
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from homefinder.models import Listing, ListingSource, Photo, PriceHistory, Reaction

RADIUS_M = 50
AREA_TOL, PRICE_TOL, HASH_MAX = 0.05, 0.03, 8
FILLABLE = ["title", "description", "district", "price", "bedrooms", "bathrooms", "livings", "built_area_m2",
            "land_area_m2", "building_age_years", "street_width_m", "facing", "street_count", "deed_type",
            "has_maid_room", "has_driver_room", "has_yard", "has_elevator"]
STATUS_RANK = {"visited": 4, "bookmarked": 3, "rejected": 2, "seen": 1, "new": 0}


def _close(a, b, tol) -> bool | None:
    if a is None or b is None:
        return None
    return abs(a - b) <= tol * max(a, b)


def _hash_match(ha: list[str], hb: list[str]) -> bool:
    hs_a = [imagehash.hex_to_hash(h) for h in ha]
    hs_b = [imagehash.hex_to_hash(h) for h in hb]
    return any(x - y <= HASH_MAX for x in hs_a for y in hs_b)


def is_duplicate(a: Listing, b: Listing, a_hashes: list[str], b_hashes: list[str]) -> bool:
    areas = [r for r in (_close(a.built_area_m2, b.built_area_m2, AREA_TOL), _close(a.land_area_m2, b.land_area_m2, AREA_TOL)) if r is not None]
    if not areas or not all(areas):
        return False
    if not _close(a.price, b.price, PRICE_TOL):
        return False
    if a_hashes and b_hashes:
        return _hash_match(a_hashes, b_hashes)
    return bool(a.property_type and a.property_type == b.property_type)


def _hashes(s: Session, lid: int) -> list[str]:
    return [h for h in s.scalars(select(Photo.phash).where(Photo.listing_id == lid)) if h]


def find_duplicate(s: Session, l: Listing) -> Listing | None:
    if l.geom is None or l.geo_precision not in ("exact", "approximate"):
        return None
    cands = s.scalars(select(Listing).where(
        Listing.id != l.id, Listing.merged_into_id.is_(None), Listing.status == "active",
        Listing.geo_precision.in_(["exact", "approximate"]),
        func.ST_DWithin(Listing.geom, l.geom, RADIUS_M)).order_by(Listing.id))
    mine = _hashes(s, l.id)
    for c in cands:
        if is_duplicate(c, l, _hashes(s, c.id), mine):
            return c
    return None


def merge(s: Session, keep: Listing, dup: Listing) -> None:
    for f in FILLABLE:
        if getattr(keep, f) is None and getattr(dup, f) is not None:
            setattr(keep, f, getattr(dup, f))
    if STATUS_RANK.get(dup.family_status, 0) > STATUS_RANK.get(keep.family_status, 0):
        keep.family_status = dup.family_status
    for model in (ListingSource, Reaction, PriceHistory):
        s.execute(update(model).where(model.listing_id == dup.id).values(listing_id=keep.id))
    if not _hashes(s, keep.id):
        s.execute(update(Photo).where(Photo.listing_id == dup.id).values(listing_id=keep.id))
        keep.photos_fetched = True
    dup.merged_into_id = keep.id
    s.flush()


def dedupe_and_merge(s: Session, listing_id: int) -> int | None:
    l = s.get(Listing, listing_id)
    if l is None or l.merged_into_id:
        return None
    other = find_duplicate(s, l)
    if other is None:
        return None
    keep, dup = (other, l) if other.id < l.id else (l, other)
    merge(s, keep, dup)
    return keep.id
```
Note: moving a `Photo` row may violate `uq(listing_id, position)` when `keep` has no photos but conflicting positions. That's impossible here because we only move when `keep` has none.

- [ ] **Step 3: Hook into enrich.** At the end of `enrich_listing` (after photos are marked fetched), open a new session: `keep = dedupe_and_merge(s, listing_id)`. If `keep` is set, call `apply_score(s.get(Listing, keep), prefs.get_or_create(s))`, and add `"merged_into": keep` to the result.

- [ ] **Step 4: Run backend suite — expect PASS.** Commit:
```bash
git add backend
git commit -m "feat: duplicate detection (distance, area, price, photo hash) and merge into oldest listing"
```

---

### Task 4: Price-drop badges

**Files:**
- Modify: `backend/homefinder/server/routes/listings.py` (`card()` gets `price_drop`), `backend/tests/server/test_listings_api.py`, `web/src/components/ListingCard.tsx` (badge), `web/src/components/ListingCard.test.tsx`

**Interfaces:**
- Produces: `price_drop = {"from": int, "to": int, "at": iso}` when the latest `PriceHistory` entry is lower than the previous one and is ≤ 30 days old; otherwise `null`. The card shows a badge on the photo: `↓ {formatNumber(from - to)} ر.س` in emerald, and the price line shows the old price struck through.

- [ ] **Step 1: Failing backend test**
```python
def test_price_drop_in_card(db, family):
    from homefinder.models import PriceHistory
    l = mk(db, price=1_900_000)
    db.add(PriceHistory(listing_id=l.id, price=2_000_000)); db.flush()
    db.add(PriceHistory(listing_id=l.id, price=1_900_000)); db.commit()
    card = family.get("/api/feed").json()["items"][0]
    assert card["price_drop"]["from"] == 2_000_000 and card["price_drop"]["to"] == 1_900_000
```
- [ ] **Step 2: Implement** `_price_drops(s, ids) -> dict[int, dict]`: one query ordered by `listing_id, observed_at desc, id desc`, take the first two entries per listing, compare, and check the 30-day age. Change the signature to `card(l, photos, drop=None)` so existing callers keep working, then pass `drop` from the feed, detail and map routes. The agent tools (Task 5) also call `_price_drops` for their cards.
- [ ] **Step 3: Frontend badge + test** (render with `price_drop: {from: 2000000, to: 1900000, at: ...}` → badge text `↓ 100,000 ر.س`).
- [ ] **Step 4: Run all tests. Commit** `feat: price drop badges`.

---

### Task 5: LangGraph agent — tools, graph, budget, checkpointer

**Files:**
- Create: `backend/homefinder/server/agent/__init__.py`, `prompts.py`, `tools.py`, `graph.py`, `fallback_search.py`, `costs.py`; `backend/tests/agent/__init__.py`, `backend/tests/agent/test_tools.py`, `backend/tests/agent/fake_model.py`, `backend/tests/agent/test_graph.py`, `backend/tests/agent/evals.yaml`, `backend/tests/agent/test_evals_llm.py`
- Modify: `backend/pyproject.toml` (server extra), `backend/homefinder/models.py` (`ChatThread`), migration `0003_chat_threads`

**Interfaces:**
- Consumes: `apply_prefs_patch` (Plan 2), `listings.card`, `_photo_urls`, `jobs.enqueue`, `WorkerStatus`, `ingest_raw`, `apply_score`, `AqarAdapter` + `CurlCffiTransport`, `usage.spend`.
- Produces:
  - `models.ChatThread(id: str uuid PK, title: str, created_at, updated_at)`
  - `tools.make_tools(session_factory) -> list[BaseTool]`, with tools named exactly: `get_preferences`, `update_preferences`, `search_listings`, `get_listing`, `compare_listings`, `request_scrape`. (Plan 4 adds `get_filter_suggestions` and `apply_filter_suggestion`; Plan 5 adds `suggest_visit_trip` and `create_visit_trip`.) Each tool returns a JSON string. Tools that return listings include `"cards": [ListingCard...]`.
  - `graph.build_agent(model, tools, checkpointer)` → a compiled graph
  - `graph.get_checkpointer()` → a process-wide `PostgresSaver` over a `psycopg_pool.ConnectionPool(max_size=3)`, with `setup()` called once
  - `graph.make_chat_model() -> ChatOpenAI` (large model, `streaming=True`, `stream_usage=True`)
  - `costs.UsageCallback` (a LangChain callback handler) that calls `usage.spend("openai", cost)` from `usage_metadata` at large-model prices
  - `fallback_search.run(session_factory) -> dict` (`{"ingested": n}` or `{"blocked": true}`)
  - `prompts.SYSTEM_PROMPT` (Arabic)

- [ ] **Step 1: Dependencies + model**

Add to the `server` extra: `"langchain>=1.0", "langchain-openai>=1.0", "langgraph>=1.0", "langgraph-checkpoint-postgres>=2.0", "psycopg-pool>=3.2", "curl_cffi>=0.7"`. Then run `.venv/bin/pip install -e ".[server,worker,dev]"`.
Check the installed API: `python -c "from langchain.agents import create_agent; print(create_agent)"`. If `create_agent` is missing, use `from langgraph.prebuilt import create_react_agent` with `prompt=` in place of `system_prompt=` and note it in the commit.

Add the `ChatThread` model and migration `0003`.

- [ ] **Step 2: System prompt**

`backend/homefinder/server/agent/prompts.py`:
```python
SYSTEM_PROMPT = """أنت "مساعد بيتنا"، تساعد عائلة سعودية في البحث عن منزل لشرائه في الرياض.
- تحدث بالعربية دائماً، بأسلوب ودود ومختصر.
- قبل أي تعديل على التفضيلات، افهم الطلب ثم استخدم أداة update_preferences، ثم أخبر العائلة بالتغيير بجملة واحدة.
- للبحث استخدم search_listings على البيانات المحفوظة أولاً. إذا كانت النتائج قليلة (أقل من 3) اقترح البحث عن إعلانات جديدة واستخدم request_scrape.
- لا تخترع عقارات أو أسعار أو مسافات. كل معلومة عن عقار يجب أن تأتي من الأدوات.
- عند عرض عقارات اذكر السعر والحي وأهم سببين لتقييمها.
- القيم المفقودة اذكرها كـ"غير مذكور" ولا تخمّنها.
- أوزان العوامل بين 0 و3. أسماء العوامل: commute_school, commute_work, commute_university, commute_airport, price, built_area, land_area, building_age, street_width, facing, street_count, deed_type, bedrooms, bathrooms, maid_room, driver_room, yard, elevator.
- الفلاتر الأساسية: property_types (villa/apartment/floor/house), districts, price_max, min_bedrooms, max_commute {school/work/university/airport: دقائق}, building_age_max, street_width_min.
"""
```

- [ ] **Step 3: Failing tool tests**

`backend/tests/agent/test_tools.py`:
```python
import json

from homefinder.db import session_scope
from homefinder.models import Job, Listing, Preferences, WorkerStatus
from homefinder.server.agent.tools import make_tools


def tools():
    return {t.name: t for t in make_tools(session_scope)}


def test_tool_names():
    assert set(tools()) == {"get_preferences", "update_preferences", "search_listings", "get_listing",
                            "compare_listings", "request_scrape"}


def test_update_preferences_tool(db):
    out = json.loads(tools()["update_preferences"].invoke({"hard_filters": {"price_max": 2_000_000}, "weights": {"street_width": 2}}))
    assert out["ok"] and out["preferences"]["hard_filters"]["price_max"] == 2_000_000
    db.expire_all()
    p = db.get(Preferences, 1)
    assert "street_width" in p.locked_weights


def test_update_preferences_tool_rejects_invalid(db):
    out = json.loads(tools()["update_preferences"].invoke({"hard_filters": {"price_max": 5}}))
    assert out["ok"] is False and "price_max" in out["error"]
    assert db.get(Preferences, 1) is None or db.get(Preferences, 1).hard_filters.get("price_max") is None


def test_search_listings_tool(db):
    db.add_all([Listing(title="أ", district="النرجس", price=1_500_000, score=80, bedrooms=5),
                Listing(title="ب", district="الملقا", price=3_000_000, score=90, bedrooms=6),
                Listing(title="ج", district="النرجس", price=1_000_000, score=60, family_status="rejected")])
    db.commit()
    out = json.loads(tools()["search_listings"].invoke({"district": "حي النرجس", "max_price": 2_000_000}))
    assert [c["title"] for c in out["cards"]] == ["أ"]


def test_request_scrape_online_enqueues(db):
    from sqlalchemy import func
    db.add(WorkerStatus(id=1, last_seen=func.now())); db.commit()
    out = json.loads(tools()["request_scrape"].invoke({"note": "فلل الياسمين"}))
    assert out["mode"] == "queued" and db.query(Job).filter_by(type="scrape_search").count() == 2  # aqar + haraj


def test_request_scrape_offline_uses_fallback(db, monkeypatch):
    from homefinder.server.agent import fallback_search
    monkeypatch.setattr(fallback_search, "run", lambda sf: {"ingested": 3})
    out = json.loads(tools()["request_scrape"].invoke({"note": ""}))
    assert out == {"mode": "fallback", "ingested": 3}
```

- [ ] **Step 4: Implement tools.py**

```python
import json
from datetime import UTC, datetime, timedelta

from langchain_core.tools import tool
from sqlalchemy import select

from homefinder import jobs, prefs
from homefinder.models import Listing, WorkerStatus
from homefinder.scoring import effective_targets, effective_weights
from homefinder.server.agent import fallback_search
from homefinder.server.routes.listings import _photo_urls, card
from homefinder.server.routes.settings import PrefsPatch, apply_prefs_patch
from homefinder.textnorm import normalize_district
from homefinder.worker.scheduler import ENABLED_SOURCES

OFFLINE_AFTER = timedelta(minutes=10)


def _j(o) -> str:
    return json.dumps(o, ensure_ascii=False, default=str)


def _cards(s, rows) -> list[dict]:
    photos = _photo_urls(s, [l.id for l in rows])
    out = []
    for l in rows:
        c = card(l, photos.get(l.id))
        c["top_reasons"] = [x["factor"] for x in (l.score_breakdown or {}).get("contributions", [])[:2]]
        out.append(c)
    return out


def make_tools(session_factory):
    @tool
    def get_preferences() -> str:
        """يعرض التفضيلات الحالية: الفلاتر الأساسية والأوزان والأهداف."""
        with session_factory() as s:
            p = prefs.get_or_create(s)
            return _j({"hard_filters": p.hard_filters, "weights": effective_weights(p.weights),
                       "targets": effective_targets(p.targets), "locked_weights": p.locked_weights})

    @tool
    def update_preferences(hard_filters: dict | None = None, weights: dict | None = None, targets: dict | None = None,
                           explanation: str = "تعديل عبر المساعد") -> str:
        """يعدّل التفضيلات. hard_filters وweights وtargets تعديلات جزئية. explanation جملة عربية تشرح التغيير."""
        try:
            with session_factory() as s:
                out = apply_prefs_patch(s, PrefsPatch(hard_filters=hard_filters, weights=weights, targets=targets),
                                        "agent", explanation)
                jobs.enqueue(s, "rescore_all", {}, dedupe_key="rescore_all")
            return _j({"ok": True, "preferences": out})
        except ValueError as e:
            return _j({"ok": False, "error": str(e)})

    @tool
    def search_listings(district: str | None = None, max_price: int | None = None, min_bedrooms: int | None = None,
                        property_type: str | None = None, sort: str = "score", limit: int = 5) -> str:
        """يبحث في العقارات المحفوظة (غير المستبعدة). sort: score | price | newest. الحد الأقصى 10."""
        with session_factory() as s:
            q = select(Listing).where(Listing.merged_into_id.is_(None), Listing.status == "active",
                                      Listing.family_status != "rejected")
            if max_price:
                q = q.where(Listing.price <= max_price)
            if min_bedrooms:
                q = q.where(Listing.bedrooms >= min_bedrooms)
            if property_type:
                q = q.where(Listing.property_type == property_type)
            order = {"price": Listing.price.asc().nulls_last(), "newest": Listing.first_seen.desc()}.get(
                sort, Listing.score.desc().nulls_last())
            rows = list(s.scalars(q.order_by(order).limit(200)))
            if district:
                d = normalize_district(district)
                rows = [l for l in rows if normalize_district(l.district) == d]
            rows = rows[: max(1, min(limit, 10))]
            return _j({"count": len(rows), "cards": _cards(s, rows)})

    @tool
    def get_listing(listing_id: int) -> str:
        """يعرض كل تفاصيل عقار واحد مع شرح التقييم."""
        with session_factory() as s:
            l = s.get(Listing, listing_id)
            if l is None:
                return _j({"error": "not found"})
            c = _cards(s, [l])[0]
            c.update({k: getattr(l, k) for k in ("description", "building_age_years", "street_width_m", "facing",
                                                 "deed_type", "has_maid_room", "has_driver_room", "has_yard",
                                                 "score_breakdown", "filter_reasons")})
            return _j({"cards": [c], "listing": c})

    @tool
    def compare_listings(listing_ids: list[int]) -> str:
        """يقارن بين 2 إلى 4 عقارات."""
        with session_factory() as s:
            rows = [l for l in (s.get(Listing, i) for i in listing_ids[:4]) if l]
            return _j({"cards": _cards(s, rows)})

    @tool
    def request_scrape(note: str = "") -> str:
        """يطلب البحث عن إعلانات جديدة حسب التفضيلات الحالية."""
        with session_factory() as s:
            w = s.get(WorkerStatus, 1)
            online = bool(w and w.last_seen and datetime.now(UTC) - w.last_seen < OFFLINE_AFTER)
            if online:
                for src in ENABLED_SOURCES:
                    jobs.enqueue(s, "scrape_search", {"source": src, "from_prefs": True, "scheduled": False},
                                 dedupe_key=f"scrape:{src}", priority=10)
                return _j({"mode": "queued"})
        return _j({"mode": "fallback", **fallback_search.run(session_factory)})

    return [get_preferences, update_preferences, search_listings, get_listing, compare_listings, request_scrape]
```
Before importing `PrefsPatch` and `apply_prefs_patch` from `routes/settings.py`, make sure they have no FastAPI-request dependencies.

- [ ] **Step 5: fallback_search.py**

```python
import logging

from homefinder import prefs
from homefinder.rescore import apply_score
from homefinder.schemas import SearchQuery
from homefinder.worker.ingest import ingest_raw
from homefinder.worker.sources.aqar import AqarAdapter
from homefinder.worker.sources.aqar_transport import Blocked, CurlCffiTransport

log = logging.getLogger(__name__)


def run(session_factory) -> dict:
    with session_factory() as s:
        q = SearchQuery.from_hard_filters(prefs.get_or_create(s).hard_filters).model_copy(update={"max_pages": 1})
    q = q.model_copy(update={"districts": q.districts[:2], "property_types": q.property_types[:1]})
    t = CurlCffiTransport()
    try:
        raws = list(AqarAdapter(t).search(q))
    except Blocked as e:
        log.warning("fallback search blocked: %s", e)
        return {"blocked": True}
    finally:
        t.close()
    n = 0
    for r in raws[:20]:
        with session_factory() as s:
            ingest_raw(s, r)
            n += 1
    return {"ingested": n}
```
(`ingest_raw` already scores the listing and enqueues enrichment for when the Mac comes back.)

- [ ] **Step 6: Fake model + graph test**

`backend/tests/agent/fake_model.py`:
```python
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class ScriptedToolModel(BaseChatModel):
    """Returns pre-scripted AIMessages in order; supports bind_tools for agent graphs."""
    script: list[AIMessage]
    i: int = 0

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        msg = self.script[min(self.i, len(self.script) - 1)]
        self.i += 1
        return ChatResult(generations=[ChatGeneration(message=msg)])
```

`backend/tests/agent/test_graph.py`:
```python
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from homefinder.db import session_scope
from homefinder.models import Preferences
from homefinder.server.agent.graph import build_agent
from homefinder.server.agent.tools import make_tools
from tests.agent.fake_model import ScriptedToolModel


def test_agent_updates_preferences_and_answers(db):
    model = ScriptedToolModel(script=[
        AIMessage(content="", tool_calls=[{"name": "update_preferences", "args": {"hard_filters": {"price_max": 1_800_000}},
                                           "id": "c1", "type": "tool_call"}]),
        AIMessage(content="تم تحديد الميزانية بـ 1,800,000 ريال."),
    ])
    agent = build_agent(model, make_tools(session_scope), InMemorySaver())
    out = agent.invoke({"messages": [{"role": "user", "content": "ميزانيتنا مليون وثمانمية"}]},
                       {"configurable": {"thread_id": "t1"}})
    assert out["messages"][-1].content.startswith("تم")
    db.expire_all()
    assert db.get(Preferences, 1).hard_filters["price_max"] == 1_800_000
```

- [ ] **Step 7: Implement graph.py and costs.py**

`backend/homefinder/server/agent/graph.py`:
```python
from functools import lru_cache

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg_pool import ConnectionPool

from homefinder.config import get_settings
from homefinder.server.agent.prompts import SYSTEM_PROMPT


def build_agent(model, tools, checkpointer):
    return create_agent(model, tools=tools, system_prompt=SYSTEM_PROMPT, checkpointer=checkpointer)


def make_chat_model() -> ChatOpenAI:
    st = get_settings()
    return ChatOpenAI(model=st.openai_model_large, api_key=st.openai_api_key, streaming=True, stream_usage=True)


@lru_cache
def get_checkpointer() -> PostgresSaver:
    url = get_settings().database_url.replace("postgresql+psycopg://", "postgresql://")
    pool = ConnectionPool(url, max_size=3, kwargs={"autocommit": True, "prepare_threshold": 0})
    saver = PostgresSaver(pool)
    saver.setup()
    return saver
```

`backend/homefinder/server/agent/costs.py`:
```python
from langchain_core.callbacks import BaseCallbackHandler

from homefinder import usage
from homefinder.config import get_settings


class UsageCallback(BaseCallbackHandler):
    def on_llm_end(self, response, **kwargs):
        st = get_settings()
        for gens in response.generations:
            for g in gens:
                um = getattr(getattr(g, "message", None), "usage_metadata", None) or {}
                cost = um.get("input_tokens", 0) * st.openai_price_in_large / 1e6 + um.get("output_tokens", 0) * st.openai_price_out_large / 1e6
                if cost:
                    usage.spend("openai", cost)
```

- [ ] **Step 8: LLM evals (manual, `-m llm`)**

`backend/tests/agent/evals.yaml` has 15 cases. Each one has `messages` (user turns), `expect_tools` (names that must be called, in any order), and `expect_prefs` (dotted-key → value, checked after the conversation):
```yaml
- name: budget
  messages: ["ميزانيتنا ٢ مليون"]
  expect_tools: [update_preferences]
  expect_prefs: {hard_filters.price_max: 2000000}
- name: district_add
  messages: ["نبي بس في النرجس والياسمين"]
  expect_tools: [update_preferences]
  expect_prefs: {hard_filters.districts: ["النرجس", "الياسمين"]}
- name: weight_school_over_work
  messages: ["المدرسة أهم من الدوام"]
  expect_tools: [update_preferences]
  expect_prefs_cmp: ["weights.commute_school > weights.commute_work"]
- name: min_bedrooms
  messages: ["لازم ٥ غرف على الأقل"]
  expect_tools: [update_preferences]
  expect_prefs: {hard_filters.min_bedrooms: 5}
- name: no_old_houses
  messages: ["ما نبي بيوت عمرها فوق ١٠ سنين"]
  expect_tools: [update_preferences]
  expect_prefs: {hard_filters.building_age_max: 10}
- name: wide_street
  messages: ["الشارع لازم ٢٠ متر وفوق"]
  expect_tools: [update_preferences]
  expect_prefs: {hard_filters.street_width_min: 20}
- name: work_commute_cap
  messages: ["ما نبي أكثر من نص ساعة للدوام"]
  expect_tools: [update_preferences]
  expect_prefs: {hard_filters.max_commute.work: 30}
- name: apartments_too
  messages: ["عادي شقق بعد"]
  expect_tools: [update_preferences]
  expect_prefs_contains: {hard_filters.property_types: apartment}
- name: show_best
  messages: ["وش أفضل ٣ بيوت عندك؟"]
  expect_tools: [search_listings]
- name: show_in_district
  messages: ["عطني اللي في الملقا"]
  expect_tools: [search_listings]
- name: compare
  messages: ["قارن لي بين أول اثنين"]
  expect_tools: [search_listings, compare_listings]
- name: details
  messages: ["وش عيوب أول واحد؟"]
  expect_tools: [search_listings, get_listing]
- name: new_search
  messages: ["دوّر لنا إعلانات جديدة"]
  expect_tools: [request_scrape]
- name: show_prefs
  messages: ["وش الشروط اللي محطوطة حالياً؟"]
  expect_tools: [get_preferences]
- name: multi_turn
  messages: ["نبي فيلا", "بحدود مليونين ونص", "وقريبة من الجامعة"]
  expect_tools: [update_preferences]
  expect_prefs: {hard_filters.price_max: 2500000}
  expect_prefs_cmp: ["weights.commute_university > 0.6"]
```
`backend/tests/agent/test_evals_llm.py` is parametrized over the YAML and marked `@pytest.mark.llm`. It seeds 6 listings, runs the real model through `build_agent(make_chat_model(), make_tools(session_scope), InMemorySaver())`, records tool calls from `AIMessage.tool_calls`, and asserts the expectations. Run manually: `OPENAI_API_KEY=... .venv/bin/pytest -m llm tests/agent -v`. Report the pass rate in the commit message (target ≥ 13/15).

- [ ] **Step 9: Run `pytest` (non-llm) — expect PASS. Commit:**
```bash
git add backend
git commit -m "feat: langgraph chat agent with preference, search, compare and scrape tools; fallback search; usage tracking"
```

---

### Task 6: Chat API (SSE) and Assistant UI

**Files:**
- Create: `backend/homefinder/server/routes/chat.py`, `backend/tests/server/test_chat_api.py`
- Modify: `backend/homefinder/server/app.py` (include chat router; call `get_checkpointer()` at startup when an `OPENAI_API_KEY` is set)
- Create: `web/src/api/chat.ts`, `web/src/api/chat.test.ts`, `web/src/components/chat/ChatPanel.tsx`, `ChatMessage.tsx`, `ChatListingStrip.tsx`, `web/src/pages/AssistantPage.tsx`, `web/e2e/chat.spec.ts`
- Modify: `web/src/components/nav.ts` (add `{to: '/assistant', label: 'المساعد', icon: '💬'}` after الخريطة), `web/src/components/AppShell.tsx` (desktop docks `ChatPanel` on the end side, collapsible; tablet shows a floating 💬 button that opens a slide-over), `web/src/App.tsx` (route)

**Interfaces:**
- HTTP:
  - `POST /api/chat {message: str (1..2000), thread_id?: str}` → `text/event-stream`. Each event is `data: <json>\n\n`. Events: `{"type":"thread","thread_id"}` (first), `{"type":"token","text"}`, `{"type":"tool","name"}`, `{"type":"listings","items":[ListingCard]}`, `{"type":"prefs_changed"}`, `{"type":"error","message"}`, `{"type":"done"}`.
  - `GET /api/chat/threads` → `[{id, title, updated_at}]` (latest 30)
  - `GET /api/chat/threads/{id}` → `{id, title, messages: [{role: "user"|"assistant", text, listings?: ListingCard[]}]}`
  - `POST /api/chat/threads` → `{id}`
- Frontend:
  - `streamChat(message, threadId, onEvent, signal) -> Promise<void>`, parsing SSE from `fetch` + `ReadableStream`
  - `parseSSE(chunk: string, buffer: string) -> {events: object[], rest: string}`
  - `<ChatPanel variant="page"|"docked"|"overlay" onClose?>`

- [ ] **Step 1: Failing backend tests**

`backend/tests/server/test_chat_api.py`:
```python
import json

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver

from tests.agent.fake_model import ScriptedToolModel


def events(resp):
    return [json.loads(line[6:]) for line in resp.text.split("\n") if line.startswith("data: ")]


@pytest.fixture
def fake_agent(monkeypatch):
    from homefinder.server.routes import chat
    saver = InMemorySaver()
    def factory(script):
        monkeypatch.setattr(chat, "get_checkpointer", lambda: saver)
        monkeypatch.setattr(chat, "make_chat_model", lambda: ScriptedToolModel(script=script))
    return factory


def test_chat_streams_tokens_listings_and_done(db, family, fake_agent):
    from homefinder.models import Listing
    db.add(Listing(title="فيلا", district="النرجس", price=1_500_000, score=80)); db.commit()
    fake_agent([AIMessage(content="", tool_calls=[{"name": "search_listings", "args": {}, "id": "c1", "type": "tool_call"}]),
                AIMessage(content="وجدت فيلا واحدة.")])
    r = family.post("/api/chat", json={"message": "وش عندك؟"})
    ev = events(r)
    assert ev[0]["type"] == "thread" and ev[-1]["type"] == "done"
    assert any(e["type"] == "tool" and e["name"] == "search_listings" for e in ev)
    assert any(e["type"] == "listings" and e["items"][0]["title"] == "فيلا" for e in ev)
    assert "".join(e["text"] for e in ev if e["type"] == "token") == "وجدت فيلا واحدة."
    tid = ev[0]["thread_id"]
    hist = family.get(f"/api/chat/threads/{tid}").json()
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant"]
    assert hist["messages"][1]["listings"][0]["title"] == "فيلا"


def test_chat_budget_exceeded(db, family, fake_agent, settings_env, monkeypatch):
    from homefinder import usage
    def boom(provider, cost): raise usage.BudgetExceeded("cap")
    monkeypatch.setattr(usage, "spend", boom)
    fake_agent([AIMessage(content="should not be called")])
    ev = events(family.post("/api/chat", json={"message": "هلا"}))
    assert ev[-1] == {"type": "error", "message": "تم الوصول إلى الحد الشهري لاستخدام المساعد"}
    assert not any(e["type"] == "token" for e in ev)


def test_chat_requires_login(app_client):
    assert app_client.post("/api/chat", json={"message": "x"}).status_code == 401


def test_chat_validates_message(family):
    assert family.post("/api/chat", json={"message": ""}).status_code == 422


def test_chat_client_disconnect(db, family, fake_agent):
    from homefinder.server.routes import chat
    fake_agent([AIMessage(content="رد طويل " * 50)])
    gen = chat._event_stream("مرحبا", None, disconnected=lambda: True)
    first = next(gen)
    assert '"thread"' in first
    assert list(gen) == []  # stops quietly once disconnected
```

- [ ] **Step 2: Implement routes/chat.py**

```python
import json
import logging
import uuid
from collections.abc import Callable, Iterator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homefinder import usage
from homefinder.db import session_scope
from homefinder.models import ChatThread
from homefinder.server.agent.costs import UsageCallback
from homefinder.server.agent.graph import build_agent, get_checkpointer, make_chat_model
from homefinder.server.agent.tools import make_tools
from homefinder.server.deps import get_db, require_family

log = logging.getLogger(__name__)
router = APIRouter(dependencies=[Depends(require_family)])
BUDGET_MSG = "تم الوصول إلى الحد الشهري لاستخدام المساعد"
LISTING_TOOLS = {"search_listings", "get_listing", "compare_listings"}


class ChatBody(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    thread_id: str | None = None


def _sse(o: dict) -> str:
    return f"data: {json.dumps(o, ensure_ascii=False)}\n\n"


def _ensure_thread(thread_id: str | None, first_message: str) -> str:
    with session_scope() as s:
        if thread_id and s.get(ChatThread, thread_id):
            s.get(ChatThread, thread_id).updated_at = func.now()
            return thread_id
        tid = str(uuid.uuid4())
        s.add(ChatThread(id=tid, title=first_message[:60]))
        return tid


def _event_stream(message: str, thread_id: str | None, disconnected: Callable[[], bool]) -> Iterator[str]:
    tid = _ensure_thread(thread_id, message)
    yield _sse({"type": "thread", "thread_id": tid})
    try:
        usage.spend("openai", 0.0)
    except usage.BudgetExceeded:
        yield _sse({"type": "error", "message": BUDGET_MSG})
        return
    agent = build_agent(make_chat_model(), make_tools(session_scope), get_checkpointer())
    config = {"configurable": {"thread_id": tid}, "callbacks": [UsageCallback()]}
    try:
        for mode, data in agent.stream({"messages": [HumanMessage(message)]}, config, stream_mode=["messages", "updates"]):
            if disconnected():
                return
            if mode == "messages":
                chunk, _meta = data
                if isinstance(chunk, AIMessageChunk) and chunk.content and not chunk.tool_call_chunks:
                    yield _sse({"type": "token", "text": chunk.content if isinstance(chunk.content, str) else ""})
            elif mode == "updates":
                for _node, upd in data.items():
                    for m in (upd or {}).get("messages", []):
                        if isinstance(m, AIMessage):
                            for tc in m.tool_calls:
                                yield _sse({"type": "tool", "name": tc["name"]})
                        if isinstance(m, ToolMessage):
                            payload = json.loads(m.content) if isinstance(m.content, str) and m.content.startswith("{") else {}
                            if m.name in LISTING_TOOLS and payload.get("cards"):
                                yield _sse({"type": "listings", "items": payload["cards"]})
                            if m.name == "update_preferences" and payload.get("ok"):
                                yield _sse({"type": "prefs_changed"})
    except usage.BudgetExceeded:
        yield _sse({"type": "error", "message": BUDGET_MSG})
        return
    except Exception:  # noqa: BLE001
        log.exception("chat failed")
        yield _sse({"type": "error", "message": "حدث خطأ، حاول مرة أخرى"})
        return
    yield _sse({"type": "done"})


@router.post("/chat")
async def chat(body: ChatBody, request: Request):
    state = {"gone": False}

    def disconnected() -> bool:
        return state["gone"]

    def gen():
        for chunk in _event_stream(body.message, body.thread_id, disconnected):
            yield chunk

    async def watch():
        async for chunk in iterate_in_threadpool(gen()):
            if await request.is_disconnected():
                state["gone"] = True
                break
            yield chunk

    return StreamingResponse(watch(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```
Add `from starlette.concurrency import iterate_in_threadpool`. Also add the thread routes. `GET /chat/threads/{id}` reads `agent.get_state({"configurable": {"thread_id": id}}).values["messages"]` from a graph built with `build_agent(make_chat_model(), make_tools(session_scope), get_checkpointer())` (no LLM call happens). It maps `HumanMessage` → user and `AIMessage` with content → assistant, and attaches `listings` from the `ToolMessage`s between them (listing tools only). It returns 404 for an unknown thread.

- [ ] **Step 3: Run backend tests — expect PASS.**

- [ ] **Step 4: Frontend SSE client with test**

`web/src/api/chat.test.ts`:
```ts
import { expect, it } from 'vitest'
import { parseSSE } from './chat'

it('parses complete events and keeps partial rest', () => {
  const { events, rest } = parseSSE('data: {"type":"token","text":"مر"}\n\ndata: {"type":"tok', '')
  expect(events).toEqual([{ type: 'token', text: 'مر' }])
  expect(rest).toBe('data: {"type":"tok')
  const second = parseSSE('en","text":"حبا"}\n\n', rest)
  expect(second.events).toEqual([{ type: 'token', text: 'حبا' }])
})
```

`web/src/api/chat.ts`:
```ts
import type { ListingCard } from './types'

export type ChatEvent =
  | { type: 'thread'; thread_id: string } | { type: 'token'; text: string } | { type: 'tool'; name: string }
  | { type: 'listings'; items: ListingCard[] } | { type: 'prefs_changed' } | { type: 'error'; message: string } | { type: 'done' }

export function parseSSE(chunk: string, buffer: string): { events: ChatEvent[]; rest: string } {
  const text = buffer + chunk
  const parts = text.split('\n\n')
  const rest = parts.pop() ?? ''
  const events = parts.flatMap((p) => p.split('\n').filter((l) => l.startsWith('data: ')).map((l) => JSON.parse(l.slice(6)) as ChatEvent))
  return { events, rest }
}

export async function streamChat(message: string, threadId: string | null, onEvent: (e: ChatEvent) => void, signal?: AbortSignal) {
  const r = await fetch('/api/chat', {
    method: 'POST', credentials: 'include', signal,
    headers: { 'content-type': 'application/json' }, body: JSON.stringify({ message, thread_id: threadId }),
  })
  if (r.status === 401) { location.assign('/login'); return }
  if (!r.ok || !r.body) { onEvent({ type: 'error', message: 'تعذّر الاتصال بالمساعد' }); return }
  const reader = r.body.pipeThrough(new TextDecoderStream()).getReader()
  let rest = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    const out = parseSSE(value, rest)
    rest = out.rest
    out.events.forEach(onEvent)
  }
}
```

- [ ] **Step 5: ChatPanel**

Behavior of `<ChatPanel variant>`:
- **Header:** title "المساعد", a "محادثة جديدة" (new conversation) button that resets the `threadId`, and a threads dropdown (`GET /api/chat/threads`; picking one loads `GET /api/chat/threads/{id}`). `onClose` shows an ✕ in the overlay and docked variants.
- **Messages:** user bubbles on the start side (brand background), assistant bubbles on the end side (white). Assistant text keeps line breaks.
- **Inline listings:** `<ChatListingStrip items>`, a horizontal snap-scroll of compact cards (photo, price, district, score). Tapping one opens `/?id=<id>` on tablet/desktop or `/listing/<id>` on phone.
- **While streaming:** append tokens to the last assistant bubble. Show the current tool as a status line: `search_listings` → "يبحث في العقارات…" (searching listings), `update_preferences` → "يحدّث التفضيلات…" (updating preferences), `request_scrape` → "يطلب إعلانات جديدة…" (requesting new listings), `compare_listings` → "يقارن…" (comparing), `get_listing` → "يقرأ التفاصيل…" (reading details), `get_preferences` → "يراجع التفضيلات…" (reviewing preferences).
- **On `prefs_changed`:** invalidate the `['feed']`, `['map']` and `['preferences']` queries.
- **On `error`:** show a red system bubble with the message.
- **Input:** a textarea (Enter sends, Shift+Enter makes a newline), disabled while streaming. A stop button aborts via `AbortController`. Suggested prompt chips appear when the thread is empty: "وش أفضل البيوت حالياً؟" (what are the best houses right now?), "غيّر الميزانية", "دوّر إعلانات جديدة" (look for new listings).
- **Persistence:** `threadId` lives in `localStorage` key `hf_thread` (wrapped in try/catch).
- **Variants:**
  - `page`: full height.
  - `docked` (desktop): 380px wide column on the end side, collapsible to a 48px rail with 💬. State is in `localStorage` `hf_chat_open`.
  - `overlay` (tablet): fixed slide-over on the end side, 420px wide, full height, with a backdrop.

- [ ] **Step 6: e2e** — `web/e2e/chat.spec.ts`. Mock `POST /api/chat` to `route.fulfill` an SSE body with `thread`, `tool`, `listings` (one card), `token`s and `done`. Assert per viewport:
  - phone: navigating to the المساعد tab shows the full-page chat.
  - tablet: the floating 💬 button opens the overlay.
  - desktop: the docked panel is visible next to the feed.
  - In every case: sending "وش عندك؟" shows the streamed text and a listing card in the strip, and a "محادثة جديدة" click clears the messages.

- [ ] **Step 7: Run all tests + RTL grep. Commit:**
```bash
git add backend web
git commit -m "feat: streaming arabic chat assistant with inline listing cards, docked/overlay/page layouts"
```

## Plan 3 done when
All non-llm tests pass. `pytest -m llm` scores ≥ 13/15 with a real key, or the result is reported. The api container idles under 450 MiB.
