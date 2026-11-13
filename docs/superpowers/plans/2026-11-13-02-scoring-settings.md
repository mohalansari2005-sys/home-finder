# Plan 2 — Scoring, Hard Filters, Settings

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every listing gets an explainable 0–100 score and a hard-filter verdict. The feed is ranked by score. The family can edit places, filters and weights in a full Settings screen, and the detail view shows why a listing scored the way it did.

**Architecture:** `homefinder/scoring.py` is pure (no DB, no I/O) and is shared by server and worker. `homefinder/rescore.py` applies it to ORM rows. The worker scores on ingest and enrich; the server rescores everything in a FastAPI background task when preferences change, so changes show up even while the Mac is asleep. Commute recompute after a place change is a worker job (it needs Google).

**Tech Stack:** As overview.

**Spec:** `docs/superpowers/specs/2026-11-13-home-finder-design.md` §3.3, §3.7 (Settings, Detail), §4 (`preferences`, `preference_changes`)

## Global Constraints

All constraints in `2026-11-13-00-overview.md`. Plan 1 must be complete and green.

## Review Focus

1. **A listing with almost no data** (only a price): it still gets a score from the factors present, every other factor appears in `missing`, and nothing crashes. Pinned in `test_score_with_mostly_missing`.
2. **District names spelled differently** ("حي النرجس" vs "النرجس" vs "النرجس " with إ/ا variants) match the district hard filter. Pinned in `test_district_filter_normalizes`.
3. **All weights set to 0:** score is `None` and the UI shows "—" instead of dividing by zero. Pinned in `test_all_zero_weights`.
4. **Invalid preference input** (unknown factor, negative weight, price_max 5) returns 422 and leaves stored preferences untouched. Pinned in `test_put_preferences_validation`.
5. **Unknown values never fail a hard filter** (bedrooms `None` with a `min_bedrooms` filter set → passes). Pinned in `test_unknown_values_pass_filters`.

---

### Task 1: Pure scoring module

**Files:**
- Create: `backend/homefinder/scoring.py`, `backend/tests/test_scoring.py`

**Interfaces:**
- Produces:
  - `FACTORS: list[str]` = `["commute_school","commute_work","commute_university","commute_airport","price","built_area","land_area","building_age","street_width","facing","street_count","deed_type","bedrooms","bathrooms","maid_room","driver_room","yard","elevator"]`
  - `DEFAULT_WEIGHTS: dict[str, float]`, `DEFAULT_TARGETS: dict`
  - `effective_weights(weights: dict) -> dict`, `effective_targets(targets: dict) -> dict`
  - `factor_values(l, hard_filters: dict, targets: dict) -> dict[str, float | None]` (`l` is any object with Listing attributes)
  - `passes_hard_filters(l, hard_filters: dict) -> tuple[bool, list[str]]`
  - `ScoreResult` dataclass `(total: float | None, contributions: list[dict], missing: list[str])` with `as_dict()`
  - `score(l, hard_filters, weights, targets) -> ScoreResult`

- [ ] **Step 1: Write failing tests**

`backend/tests/test_scoring.py`:
```python
from types import SimpleNamespace

import pytest

from homefinder.scoring import DEFAULT_WEIGHTS, FACTORS, factor_values, passes_hard_filters, score

HF = {"price_max": 2_000_000, "min_bedrooms": 4, "property_types": ["villa"], "districts": ["النرجس"],
      "max_commute": {"work": 40}, "building_age_max": 15, "street_width_min": 15}


def L(**kw):
    base = {f: None for f in ["price", "bedrooms", "bathrooms", "built_area_m2", "land_area_m2", "building_age_years",
                              "street_width_m", "facing", "street_count", "deed_type", "has_maid_room",
                              "has_driver_room", "has_yard", "has_elevator", "property_type", "district"]}
    base["commutes"] = {}
    base.update(kw)
    return SimpleNamespace(**base)


def test_factor_values_normalization():
    v = factor_values(L(price=1_400_000, commutes={"work": 10, "school": 40, "university": 25}, built_area_m2=350,
                        building_age_years=0, street_width_m=20, street_count=2, has_maid_room=True,
                        has_yard=False, bedrooms=5, bathrooms=5, deed_type="electronic"), HF, {})
    assert v["price"] == 1.0                      # <= 70% of max
    assert v["commute_work"] == 1.0 and v["commute_school"] == 0.0 and v["commute_university"] == pytest.approx(0.5)
    assert v["built_area"] == 1.0 and v["building_age"] == 1.0 and v["street_width"] == 1.0
    assert v["street_count"] == 0.7 and v["maid_room"] == 1.0 and v["yard"] == 0.0
    assert v["bedrooms"] == 1.0 and v["bathrooms"] == 1.0 and v["deed_type"] == 1.0
    assert v["commute_airport"] is None and v["facing"] is None  # facing: no preferred facings configured


def test_price_linear_between_70_and_100_percent():
    assert factor_values(L(price=1_700_000), HF, {})["price"] == pytest.approx(0.5)
    assert factor_values(L(price=2_100_000), HF, {})["price"] == 0.0
    assert factor_values(L(price=1_000_000), {}, {})["price"] is None  # no budget configured


def test_facing_with_preference():
    assert factor_values(L(facing="north"), HF, {"preferred_facings": ["north", "east"]})["facing"] == 1.0
    assert factor_values(L(facing="west"), HF, {"preferred_facings": ["north"]})["facing"] == 0.0


def test_score_explains():
    r = score(L(price=1_400_000, commutes={"work": 10}, building_age_years=30), HF, {}, {})
    assert 0 <= r.total <= 100
    by = {c["factor"]: c for c in r.contributions}
    assert by["price"]["delta"] > 0 and by["building_age"]["delta"] < 0
    assert r.contributions == sorted(r.contributions, key=lambda c: -c["delta"])
    assert "street_width" in r.missing
    d = r.as_dict()
    assert set(d) == {"total", "contributions", "missing"}


def test_score_with_mostly_missing():
    r = score(L(price=1_000_000), HF, {}, {})
    assert r.total == 100.0 and len(r.contributions) == 1 and len(r.missing) == len([f for f in FACTORS if DEFAULT_WEIGHTS[f] > 0]) - 1


def test_all_zero_weights():
    r = score(L(price=1_000_000), HF, {f: 0 for f in FACTORS}, {})
    assert r.total is None and r.contributions == []


def test_weights_override_defaults():
    a = score(L(price=1_000_000, building_age_years=40), HF, {}, {}).total
    b = score(L(price=1_000_000, building_age_years=40), HF, {"building_age": 0}, {}).total
    assert b > a


def test_hard_filters_reasons():
    ok, reasons = passes_hard_filters(L(price=2_500_000, bedrooms=3, property_type="apartment", district="الملقا",
                                        commutes={"work": 55}, building_age_years=20, street_width_m=10), HF)
    assert not ok and set(reasons) == {"price_above_max", "bedrooms_below_min", "type_excluded", "district_excluded",
                                       "commute_work_too_long", "too_old", "street_too_narrow"}


def test_unknown_values_pass_filters():
    assert passes_hard_filters(L(), HF) == (True, [])


def test_district_filter_normalizes():
    for d in ["حي النرجس", "النرجس ", "النّرجس"]:
        assert passes_hard_filters(L(district=d), {"districts": ["النرجس"]})[0], d
    assert passes_hard_filters(L(district="الأندلس"), {"districts": ["حي الاندلس"]})[0]
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement scoring.py**

```python
from dataclasses import asdict, dataclass, field

from homefinder.textnorm import normalize_district

COMMUTE_KINDS = ["school", "work", "university", "airport"]
FACTORS = [f"commute_{k}" for k in COMMUTE_KINDS] + [
    "price", "built_area", "land_area", "building_age", "street_width", "facing", "street_count", "deed_type",
    "bedrooms", "bathrooms", "maid_room", "driver_room", "yard", "elevator"]

DEFAULT_WEIGHTS = {
    "commute_school": 1.0, "commute_work": 1.0, "commute_university": 0.6, "commute_airport": 0.2,
    "price": 1.0, "built_area": 0.6, "land_area": 0.4, "building_age": 0.6, "street_width": 0.5,
    "facing": 0.2, "street_count": 0.2, "deed_type": 0.3, "bedrooms": 0.4, "bathrooms": 0.3,
    "maid_room": 0.3, "driver_room": 0.2, "yard": 0.3, "elevator": 0.2,
}
DEFAULT_TARGETS = {
    "commute_good_min": 10, "commute_bad_min": 40,
    "built_area_ideal": 350, "land_area_ideal": 400,
    "age_bad_years": 20, "street_good_m": 20, "street_bad_m": 10,
    "preferred_facings": [], "bedrooms_ideal": 5,
}
BOOL_FACTORS = {"maid_room": "has_maid_room", "driver_room": "has_driver_room", "yard": "has_yard", "elevator": "has_elevator"}


def effective_weights(weights: dict | None) -> dict[str, float]:
    return {**DEFAULT_WEIGHTS, **{k: float(v) for k, v in (weights or {}).items() if k in DEFAULT_WEIGHTS}}


def effective_targets(targets: dict | None) -> dict:
    return {**DEFAULT_TARGETS, **(targets or {})}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _lin_down(v, good, bad):
    """1 at <= good, 0 at >= bad."""
    if v is None:
        return None
    if bad == good:
        return 1.0 if v <= good else 0.0
    return _clamp((bad - v) / (bad - good))


def _lin_up(v, ideal, floor_ratio=0.6):
    """1 at >= ideal, 0 at <= floor_ratio*ideal."""
    if v is None or not ideal:
        return None
    lo = ideal * floor_ratio
    return _clamp((v - lo) / (ideal - lo))


def factor_values(l, hard_filters: dict, targets: dict) -> dict[str, float | None]:
    t = effective_targets(targets)
    commutes = getattr(l, "commutes", None) or {}
    v: dict[str, float | None] = {}
    for k in COMMUTE_KINDS:
        v[f"commute_{k}"] = _lin_down(commutes.get(k), t["commute_good_min"], t["commute_bad_min"])
    pmax = (hard_filters or {}).get("price_max")
    v["price"] = _lin_down(l.price, 0.7 * pmax, pmax) if (pmax and l.price) else None
    v["built_area"] = _lin_up(l.built_area_m2, t["built_area_ideal"])
    v["land_area"] = _lin_up(l.land_area_m2, t["land_area_ideal"])
    v["building_age"] = _lin_down(l.building_age_years, 0, t["age_bad_years"])
    v["street_width"] = _lin_down(-l.street_width_m if l.street_width_m is not None else None,
                                  -t["street_good_m"], -t["street_bad_m"])
    pref = t["preferred_facings"]
    v["facing"] = (1.0 if l.facing in pref else 0.0) if (pref and l.facing) else None
    sc = l.street_count
    v["street_count"] = None if sc is None else (0.0 if sc <= 1 else 0.7 if sc == 2 else 1.0)
    v["deed_type"] = None if l.deed_type is None else (1.0 if l.deed_type == "electronic" else 0.5)
    ideal = t["bedrooms_ideal"]
    v["bedrooms"] = None if l.bedrooms is None else _clamp(1 - 0.34 * max(0, ideal - l.bedrooms))
    v["bathrooms"] = None if (l.bathrooms is None or not l.bedrooms) else _clamp(l.bathrooms / l.bedrooms)
    for f, attr in BOOL_FACTORS.items():
        b = getattr(l, attr)
        v[f] = None if b is None else (1.0 if b else 0.0)
    return v


def passes_hard_filters(l, hf: dict) -> tuple[bool, list[str]]:
    hf = hf or {}
    r: list[str] = []
    if hf.get("price_max") and l.price and l.price > hf["price_max"]:
        r.append("price_above_max")
    if hf.get("min_bedrooms") and l.bedrooms is not None and l.bedrooms < hf["min_bedrooms"]:
        r.append("bedrooms_below_min")
    if hf.get("property_types") and l.property_type and l.property_type not in hf["property_types"]:
        r.append("type_excluded")
    if hf.get("districts") and l.district:
        allowed = {normalize_district(d) for d in hf["districts"]}
        if normalize_district(l.district) not in allowed:
            r.append("district_excluded")
    commutes = getattr(l, "commutes", None) or {}
    for kind, mx in (hf.get("max_commute") or {}).items():
        m = commutes.get(kind)
        if m is not None and mx and m > mx:
            r.append(f"commute_{kind}_too_long")
    if hf.get("building_age_max") is not None and l.building_age_years is not None and l.building_age_years > hf["building_age_max"]:
        r.append("too_old")
    if hf.get("street_width_min") and l.street_width_m is not None and l.street_width_m < hf["street_width_min"]:
        r.append("street_too_narrow")
    return (not r, r)


@dataclass
class ScoreResult:
    total: float | None
    contributions: list[dict] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def score(l, hard_filters: dict, weights: dict, targets: dict) -> ScoreResult:
    w = effective_weights(weights)
    vals = factor_values(l, hard_filters, targets)
    present = {f: x for f, x in vals.items() if x is not None and w.get(f, 0) > 0}
    missing = [f for f, x in vals.items() if x is None and w.get(f, 0) > 0]
    total_w = sum(w[f] for f in present)
    if total_w == 0:
        return ScoreResult(None, [], missing)
    total = 100 * sum(w[f] * x for f, x in present.items()) / total_w
    contrib = [{"factor": f, "value": round(x, 3), "weight": w[f], "delta": round(100 * w[f] * (x - 0.5) / total_w, 1)}
               for f, x in present.items()]
    contrib.sort(key=lambda c: -c["delta"])
    return ScoreResult(round(total, 1), contrib, missing)
```

- [ ] **Step 4: Run — expect PASS.** Then commit:
```bash
git add backend/homefinder/scoring.py backend/tests/test_scoring.py
git commit -m "feat: pure explainable scoring and hard filters"
```

---

### Task 2: Rescoring hooks, preference changes table, worker jobs

**Files:**
- Create: `backend/homefinder/rescore.py`, `backend/tests/test_rescore.py`, `backend/alembic/versions/0002_preference_changes.py`
- Modify: `backend/homefinder/models.py` (add `PreferenceChange`), `backend/homefinder/worker/ingest.py` (score after ingest), `backend/homefinder/worker/enrich/pipeline.py` (score at end), `backend/homefinder/worker/handlers.py` (register `rescore_all`, `recompute_commutes`; scrape uses `from_prefs`), `backend/homefinder/worker/scheduler.py` and `backend/homefinder/cli.py` (enqueue with `{"source": s, "from_prefs": True}`)

**Interfaces:**
- Produces:
  - `models.PreferenceChange(id, at, source: "user"|"learner"|"agent", diff: dict, explanation: str)`
  - `rescore.apply_score(listing, prefs) -> None` (sets `passes_filters`, `filter_reasons`, `score`, `score_breakdown`)
  - `rescore.rescore_all(s) -> int`
  - `rescore.record_change(s, source, before: dict, after: dict, explanation: str) -> PreferenceChange | None` (returns None when nothing changed; `diff` = `{key: {"from": .., "to": ..}}` over flattened `hard_filters.*`, `weights.*`, `targets.*`)
  - Job handlers: `rescore_all` (`{}` → `{"rescored": n}`), `recompute_commutes` (`{}` → recomputes commutes for every listing with coordinates, then rescores, returns `{"listings": n}`)
  - `scrape_search` payload accepts `{"source", "from_prefs": true}`; with `from_prefs` the query is built at run time from current preferences.

- [ ] **Step 1: Model + migration**

Add to `models.py`:
```python
class PreferenceChange(Base):
    __tablename__ = "preference_changes"
    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = _now()
    source: Mapped[str] = mapped_column(String(10))
    diff: Mapped[dict] = mapped_column(JSONB)
    explanation: Mapped[str] = mapped_column(Text)
```
Generate the migration the same way as Plan 1 Task 1 Step 8, with `--rev-id 0002 -m preference_changes`, against a DB upgraded to 0001. Then run `alembic check` and confirm no pending operations.

- [ ] **Step 2: Failing tests**

`backend/tests/test_rescore.py`:
```python
from homefinder import prefs
from homefinder.db import session_scope
from homefinder.models import Listing, PreferenceChange
from homefinder.rescore import apply_score, record_change, rescore_all
from homefinder.schemas import CanonicalFields, RawListing
from homefinder.worker.handlers import WorkerDeps, dispatch
from homefinder.worker.ingest import ingest_raw


def test_apply_score_sets_fields(db):
    p = prefs.get_or_create(db); p.hard_filters = {**p.hard_filters, "price_max": 2_000_000, "min_bedrooms": 6}
    l = Listing(price=1_000_000, bedrooms=5); db.add(l); db.flush()
    apply_score(l, p)
    assert l.passes_filters is False and l.filter_reasons == ["bedrooms_below_min"]
    assert l.score is not None and l.score_breakdown["total"] == l.score


def test_rescore_all_skips_merged(db):
    a = Listing(price=1_000_000); db.add(a); db.flush()
    db.add(Listing(price=1_000_000, merged_into_id=a.id)); db.commit()
    assert rescore_all(db) == 1


def test_ingest_scores_new_listing(db):
    r = ingest_raw(db, RawListing(source="aqar", source_id="1", url="u", fields=CanonicalFields(price=1_000_000, bedrooms=5)))
    assert db.get(Listing, r.listing_id).score_breakdown is not None


def test_record_change_diff(db):
    before = {"hard_filters": {"price_max": 1}, "weights": {"price": 1.0}, "targets": {}}
    after = {"hard_filters": {"price_max": 2}, "weights": {"price": 1.0}, "targets": {}}
    c = record_change(db, "user", before, after, "تعديل الميزانية")
    assert c.diff == {"hard_filters.price_max": {"from": 1, "to": 2}}
    assert record_change(db, "user", after, after, "x") is None
    assert db.query(PreferenceChange).count() == 1


def test_rescore_job(db):
    db.add(Listing(price=1_000_000)); db.commit()
    deps = WorkerDeps(session_factory=session_scope, adapters={}, llm=None, google=None, photo_sink=None, http=None)
    assert dispatch(deps, "rescore_all", {}) == {"rescored": 1}
```

- [ ] **Step 3: Implement rescore.py**

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder import prefs as prefs_mod
from homefinder.models import Listing, PreferenceChange, Preferences
from homefinder.scoring import passes_hard_filters, score


def apply_score(listing: Listing, p: Preferences) -> None:
    ok, reasons = passes_hard_filters(listing, p.hard_filters)
    listing.passes_filters, listing.filter_reasons = ok, reasons
    r = score(listing, p.hard_filters, p.weights, p.targets)
    listing.score, listing.score_breakdown = r.total, r.as_dict()


def rescore_all(s: Session) -> int:
    p = prefs_mod.get_or_create(s)
    n = 0
    for l in s.scalars(select(Listing).where(Listing.merged_into_id.is_(None)).execution_options(yield_per=500)):
        apply_score(l, p)
        n += 1
    s.flush()
    return n


def _flat(d: dict) -> dict:
    out = {}
    for section in ("hard_filters", "weights", "targets"):
        for k, v in (d.get(section) or {}).items():
            out[f"{section}.{k}"] = v
    return out


def record_change(s: Session, source: str, before: dict, after: dict, explanation: str) -> PreferenceChange | None:
    b, a = _flat(before), _flat(after)
    diff = {k: {"from": b.get(k), "to": a.get(k)} for k in sorted(set(b) | set(a)) if b.get(k) != a.get(k)}
    if not diff:
        return None
    c = PreferenceChange(source=source, diff=diff, explanation=explanation)
    s.add(c)
    s.flush()
    return c


def snapshot(p: Preferences) -> dict:
    return {"hard_filters": dict(p.hard_filters), "weights": dict(p.weights), "targets": dict(p.targets)}
```

- [ ] **Step 4: Wire hooks**
- `ingest_raw`: before the final `s.flush()` in both branches, call `apply_score(listing, prefs.get_or_create(s))` (import inside the function to avoid cycles).
- `enrich_listing`: after commutes are computed, call `apply_score(l, prefs.get_or_create(s))`.
- `handlers.py`:
```python
from homefinder import prefs
from homefinder.models import Listing
from homefinder.rescore import apply_score, rescore_all
from homefinder.worker.enrich.commute import compute_commutes

def handle_rescore_all(deps, payload):
    with deps.session_factory() as s:
        return {"rescored": rescore_all(s)}

def handle_recompute_commutes(deps, payload):
    if deps.google is None:
        return {"skipped": "no google key"}
    n = 0
    with deps.session_factory() as s:
        ids = list(s.scalars(select(Listing.id).where(Listing.lat.is_not(None), Listing.merged_into_id.is_(None))))
    for lid in ids:
        with deps.session_factory() as s:
            l = s.get(Listing, lid)
            l.commutes = compute_commutes(s, deps.google, l)
            apply_score(l, prefs.get_or_create(s))
            n += 1
    return {"listings": n}

HANDLERS["rescore_all"] = handle_rescore_all
HANDLERS["recompute_commutes"] = handle_recompute_commutes
```
  In `handle_scrape_search`, build the query as:
```python
if payload.get("from_prefs"):
    with deps.session_factory() as s:
        query = SearchQuery.from_hard_filters(prefs.get_or_create(s).hard_filters)
else:
    query = SearchQuery(**payload.get("query", {}))
```
- `scheduler.maybe_schedule` and `cli enqueue-scrape`: payload `{"source": source, "from_prefs": True, "scheduled": True|False}`. Update `test_scheduler.py` to assert `payload["from_prefs"] is True` instead of checking `query`.

- [ ] **Step 5: Run full suite — expect PASS.** Commit:
```bash
git add backend
git commit -m "feat: score on ingest/enrich, rescore and commute recompute jobs, preference change log"
```

---

### Task 3: Preferences API validation, rescore trigger, adapters resume, richer status

**Files:**
- Modify: `backend/homefinder/server/routes/settings.py`, `backend/homefinder/server/routes/status.py`, `backend/tests/server/test_settings_api.py`
- Create: `backend/homefinder/prefs_schema.py`

**Interfaces:**
- Produces:
  - `prefs_schema.HardFilters`, `prefs_schema.Targets` (pydantic, `extra="forbid"`), `validate_weights(d) -> dict`
  - `GET /api/preferences` → `{hard_filters, weights (effective, all FACTORS), targets (effective), locked_weights, defaults: {weights, targets}}`
  - `PUT /api/preferences {hard_filters?, weights?, targets?, unlock?: [factor], reset_weights?: bool}`:
    - Weight keys sent are added to `locked_weights`. `unlock` removes keys. `reset_weights` clears `weights` and `locked_weights`.
    - Validation failure → 422 with nothing stored.
    - Records a `PreferenceChange(source="user")`.
    - Schedules a background `rescore_all`.
    - If `property_types`, `districts`, `price_max` or `city` changed, enqueues a `scrape_search` (`from_prefs`, priority 5, dedupe `scrape:<source>`) for each enabled source.
  - `GET /api/preferences/changes?limit=20` → `[{at, source, diff, explanation}]`
  - `POST /api/adapters/{source}/resume` → 204
  - `GET /api/status` gains `counts: {active, new, bookmarked, rejected, passing}` and `last_scrape_at` per adapter (= `last_success_at`).

- [ ] **Step 1: Failing tests** (append to `test_settings_api.py`)

```python
from homefinder.models import AdapterHealth, Job, Listing, PreferenceChange


def test_get_preferences_returns_effective_defaults(family):
    p = family.get("/api/preferences").json()
    assert p["weights"]["commute_work"] == 1.0 and p["targets"]["commute_bad_min"] == 40
    assert p["locked_weights"] == [] and "defaults" in p


def test_put_weights_locks_and_rescores(db, family):
    db.add(Listing(price=1_000_000)); db.commit()
    out = family.put("/api/preferences", json={"weights": {"price": 2.5}}).json()
    assert out["weights"]["price"] == 2.5 and out["locked_weights"] == ["price"]
    db.expire_all()
    assert db.query(Listing).one().score_breakdown is not None  # background task ran (TestClient runs them inline)
    assert db.query(PreferenceChange).count() == 1
    out = family.put("/api/preferences", json={"unlock": ["price"]}).json()
    assert out["locked_weights"] == []
    out = family.put("/api/preferences", json={"reset_weights": True}).json()
    assert out["weights"]["price"] == 1.0


def test_put_preferences_validation(family):
    before = family.get("/api/preferences").json()
    for bad in [{"weights": {"nonsense": 1}}, {"weights": {"price": -1}}, {"hard_filters": {"price_max": 5}},
                {"hard_filters": {"property_types": ["castle"]}}, {"targets": {"commute_bad_min": "x"}}]:
        assert family.put("/api/preferences", json=bad).status_code == 422, bad
    assert family.get("/api/preferences").json() == before


def test_search_relevant_change_enqueues_scrape(db, family):
    family.put("/api/preferences", json={"hard_filters": {"districts": ["الياسمين"]}})
    j = db.query(Job).filter(Job.type == "scrape_search").one()
    assert j.payload == {"source": "aqar", "from_prefs": True, "scheduled": False} and j.priority == 5
    family.put("/api/preferences", json={"hard_filters": {"min_bedrooms": 4}})
    assert db.query(Job).filter(Job.type == "scrape_search").count() == 1


def test_resume_adapter(db, family):
    db.add(AdapterHealth(source="aqar", status="paused", reason="x")); db.commit()
    assert family.post("/api/adapters/aqar/resume").status_code == 204
    db.expire_all()
    assert db.get(AdapterHealth, "aqar").status == "ok"


def test_changes_list(family):
    family.put("/api/preferences", json={"hard_filters": {"price_max": 2_000_000}})
    ch = family.get("/api/preferences/changes").json()
    assert ch[0]["source"] == "user" and "hard_filters.price_max" in ch[0]["diff"]
```

- [ ] **Step 2: Implement prefs_schema.py**

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from homefinder.schemas import Facing, PropertyType
from homefinder.scoring import FACTORS

CommuteKind = Literal["school", "work", "university", "airport"]


class HardFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")
    city: Literal["الرياض"] = "الرياض"
    property_types: list[PropertyType] = Field(default_factory=lambda: ["villa"], min_length=1)
    districts: list[str] = Field(default_factory=list, max_length=30)
    price_max: int | None = Field(None, ge=100_000, le=100_000_000)
    min_bedrooms: int | None = Field(None, ge=1, le=20)
    max_commute: dict[CommuteKind, int] = Field(default_factory=dict)
    building_age_max: int | None = Field(None, ge=0, le=80)
    street_width_min: float | None = Field(None, ge=4, le=100)


class Targets(BaseModel):
    model_config = ConfigDict(extra="forbid")
    commute_good_min: int = Field(10, ge=0, le=120)
    commute_bad_min: int = Field(40, ge=5, le=180)
    built_area_ideal: float = Field(350, ge=50, le=5000)
    land_area_ideal: float = Field(400, ge=50, le=20000)
    age_bad_years: int = Field(20, ge=1, le=80)
    street_good_m: float = Field(20, ge=4, le=100)
    street_bad_m: float = Field(10, ge=4, le=100)
    preferred_facings: list[Facing] = Field(default_factory=list)
    bedrooms_ideal: int = Field(5, ge=1, le=20)
    dismissed_suggestions: list[dict] = Field(default_factory=list)  # used by Plan 4


def validate_weights(d: dict) -> dict[str, float]:
    out = {}
    for k, v in d.items():
        if k not in FACTORS:
            raise ValueError(f"unknown factor {k}")
        v = float(v)
        if not 0 <= v <= 3:
            raise ValueError(f"weight {k} out of range")
        out[k] = v
    return out
```
Also validate `max_commute` values in 5..180 with a `field_validator`.

- [ ] **Step 3: Rewrite `put_prefs` / `get_prefs` in routes/settings.py**

```python
from fastapi import BackgroundTasks, HTTPException
from pydantic import ValidationError

from homefinder import adapters_state
from homefinder.db import session_scope
from homefinder.models import PreferenceChange
from homefinder.prefs_schema import HardFilters, Targets, validate_weights
from homefinder.rescore import record_change, rescore_all, snapshot
from homefinder.scoring import DEFAULT_TARGETS, DEFAULT_WEIGHTS, effective_targets, effective_weights
from homefinder.worker.scheduler import ENABLED_SOURCES

SEARCH_KEYS = {"property_types", "districts", "price_max", "city"}


def _prefs_out(p) -> dict:
    return {"hard_filters": p.hard_filters, "weights": effective_weights(p.weights),
            "targets": effective_targets(p.targets), "locked_weights": p.locked_weights,
            "defaults": {"weights": DEFAULT_WEIGHTS, "targets": DEFAULT_TARGETS}}


class PrefsPatch(BaseModel):
    hard_filters: dict | None = None
    weights: dict[str, float] | None = None
    targets: dict | None = None
    unlock: list[str] | None = None
    reset_weights: bool = False


def _background_rescore() -> None:
    with session_scope() as s:
        rescore_all(s)


def apply_prefs_patch(s: Session, body: PrefsPatch, source: str, explanation: str) -> dict:
    """Shared by the HTTP route and the chat agent. Raises ValueError on invalid input."""
    p = prefs.get_or_create(s)
    before = snapshot(p)
    try:
        hf = HardFilters(**{**p.hard_filters, **(body.hard_filters or {})}).model_dump()
        tg = Targets(**{**p.targets, **(body.targets or {})}).model_dump(exclude_defaults=True)
        new_w = validate_weights(body.weights or {})
    except (ValidationError, ValueError) as e:
        raise ValueError(str(e)) from e
    weights = {} if body.reset_weights else {**p.weights, **new_w}
    locked = [] if body.reset_weights else sorted((set(p.locked_weights) | set(new_w)) - set(body.unlock or []))
    p.hard_filters, p.targets, p.weights, p.locked_weights = hf, tg, weights, locked
    p.updated_at = func.now()
    record_change(s, source, before, snapshot(p), explanation)
    if any(before["hard_filters"].get(k) != hf.get(k) for k in SEARCH_KEYS):
        for src in ENABLED_SOURCES:
            jobs.enqueue(s, "scrape_search", {"source": src, "from_prefs": True, "scheduled": False},
                         dedupe_key=f"scrape:{src}", priority=5)
    s.flush()
    return _prefs_out(p)


@router.put("/preferences")
def put_prefs(body: PrefsPatch, background: BackgroundTasks, s: Session = Depends(get_db)):
    try:
        out = apply_prefs_patch(s, body, "user", "تعديل من صفحة الإعدادات")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    s.commit()
    background.add_task(_background_rescore)
    return out


@router.get("/preferences/changes")
def changes(limit: int = 20, s: Session = Depends(get_db)):
    rows = s.scalars(select(PreferenceChange).order_by(PreferenceChange.at.desc()).limit(min(limit, 100)))
    return [{"at": c.at.isoformat(), "source": c.source, "diff": c.diff, "explanation": c.explanation} for c in rows]


@router.post("/adapters/{source}/resume", status_code=204)
def resume(source: str, s: Session = Depends(get_db)):
    adapters_state.resume(s, source)
    return Response(status_code=204)
```
Importing `ENABLED_SOURCES` from the worker package is fine: `scheduler.py` has no worker-only dependencies. **Keep it that way.**

- [ ] **Step 4: Extend status** with `counts` (one `GROUP BY family_status` query over active, non-merged listings, plus a `passing` count) and `last_scrape_at` per adapter.

- [ ] **Step 5: Run backend suite — expect PASS.** Commit:
```bash
git add backend
git commit -m "feat: validated preferences api with locking, change log, rescore and search-triggered scrape"
```

---

### Task 4: Settings screen (places, filters, weights, history, status)

**Files:**
- Create: `web/src/pages/settings/PlacesSection.tsx`, `FiltersSection.tsx`, `WeightsSection.tsx`, `HistorySection.tsx`, `StatusSection.tsx`, `web/src/components/MapPicker.tsx`, `web/src/lib/factors.ts`, `web/src/lib/factors.test.ts`, `web/src/pages/settings/WeightsSection.test.tsx`
- Replace: `web/src/pages/SettingsPage.tsx`
- Modify: `web/src/api/hooks.ts` (`usePreferences`, `useSavePreferences`, `useSavePlaces`, `usePreferenceChanges`, `useResumeAdapter`), `web/src/api/types.ts` (`Preferences.defaults`, `PreferenceChange`, `SystemStatus.counts`), `web/e2e/fixtures.ts`, `web/e2e/settings.spec.ts`

**Interfaces:**
- Produces:
  - `FACTOR_AR: Record<Factor, string>`, `REASON_AR: Record<string, string>` (filter reasons and reject reasons), `parseLatLng(text) -> {lat, lng} | null` (accepts `"24.7, 46.6"`, Arabic digits and Google Maps URLs containing `@lat,lng` or `q=lat,lng`)
  - `<MapPicker value onChange>`: tapping the map sets a marker. Without a Maps key it falls back to a text field using `parseLatLng`.
  - `SettingsPage` sections in this order: الأماكن (places), الفلاتر الأساسية (filters), أهمية العوامل (weights), سجل التغييرات (history), حالة النظام (status). Phone: one column. Tablet/desktop: two columns (`md:grid-cols-2`) with places spanning both.

- [ ] **Step 1: factors.ts with failing test**

`web/src/lib/factors.test.ts`:
```ts
import { expect, it } from 'vitest'
import { FACTOR_AR, parseLatLng } from './factors'

it('parses coordinates from text and google maps links', () => {
  expect(parseLatLng('24.7136, 46.6753')).toEqual({ lat: 24.7136, lng: 46.6753 })
  expect(parseLatLng('٢٤٫٧١٣٦، ٤٦٫٦٧٥٣')).toEqual({ lat: 24.7136, lng: 46.6753 })
  expect(parseLatLng('https://www.google.com/maps/place/x/@24.81,46.63,15z')).toEqual({ lat: 24.81, lng: 46.63 })
  expect(parseLatLng('https://maps.google.com/?q=24.8,46.6')).toEqual({ lat: 24.8, lng: 46.6 })
  expect(parseLatLng('hello')).toBeNull()
  expect(parseLatLng('91, 46')).toBeNull()
})

it('has an Arabic label for every factor', () => {
  expect(Object.keys(FACTOR_AR)).toHaveLength(18)
})
```

`web/src/lib/factors.ts`:
```ts
export type Factor =
  | 'commute_school' | 'commute_work' | 'commute_university' | 'commute_airport' | 'price' | 'built_area' | 'land_area'
  | 'building_age' | 'street_width' | 'facing' | 'street_count' | 'deed_type' | 'bedrooms' | 'bathrooms'
  | 'maid_room' | 'driver_room' | 'yard' | 'elevator'

export const FACTOR_AR: Record<Factor, string> = {
  commute_school: 'القرب من المدرسة', commute_work: 'القرب من العمل', commute_university: 'القرب من الجامعة',
  commute_airport: 'القرب من المطار', price: 'السعر مقارنة بالميزانية', built_area: 'مساحة البناء',
  land_area: 'مساحة الأرض', building_age: 'حداثة البناء', street_width: 'عرض الشارع', facing: 'اتجاه الواجهة',
  street_count: 'عدد الشوارع', deed_type: 'نوع الصك', bedrooms: 'عدد الغرف', bathrooms: 'دورات المياه',
  maid_room: 'غرفة خادمة', driver_room: 'غرفة سائق', yard: 'حوش', elevator: 'مصعد',
}

export const REASON_AR: Record<string, string> = {
  price_above_max: 'السعر أعلى من الميزانية', bedrooms_below_min: 'الغرف أقل من المطلوب', type_excluded: 'نوع العقار غير مطلوب',
  district_excluded: 'خارج الأحياء المختارة', commute_school_too_long: 'بعيد عن المدرسة', commute_work_too_long: 'بعيد عن العمل',
  commute_university_too_long: 'بعيد عن الجامعة', commute_airport_too_long: 'بعيد عن المطار', too_old: 'قديم',
  street_too_narrow: 'الشارع ضيق', narrow_street: 'الشارع ضيق', bad_layout: 'التصميم غير مناسب', overpriced: 'السعر مرتفع',
  far: 'بعيد', other: 'سبب آخر',
}

const DIGITS: Record<string, string> = { '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9', '٫': '.', '،': ',' }

export function parseLatLng(text: string): { lat: number; lng: number } | null {
  const t = text.replace(/[٠-٩٫،]/g, (c) => DIGITS[c])
  const m = t.match(/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/) ?? t.match(/q=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/)
    ?? t.match(/^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$/)
  if (!m) return null
  const lat = Number(m[1]), lng = Number(m[2])
  if (Math.abs(lat) > 90 || Math.abs(lng) > 180) return null
  return { lat, lng }
}
```

- [ ] **Step 2: WeightsSection with failing test**

`web/src/pages/settings/WeightsSection.test.tsx`:
```tsx
import { fireEvent, render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { WeightsSection } from './WeightsSection'

const prefs = {
  hard_filters: {}, targets: {}, locked_weights: ['price'],
  weights: { commute_school: 1, commute_work: 1, commute_university: 0.6, commute_airport: 0.2, price: 2, built_area: 0.6,
    land_area: 0.4, building_age: 0.6, street_width: 0.5, facing: 0.2, street_count: 0.2, deed_type: 0.3, bedrooms: 0.4,
    bathrooms: 0.3, maid_room: 0.3, driver_room: 0.2, yard: 0.3, elevator: 0.2 },
  defaults: { weights: {}, targets: {} },
}

it('shows lock state and saves a changed weight', () => {
  const save = vi.fn()
  render(<WeightsSection prefs={prefs as never} onSave={save} />)
  expect(screen.getByLabelText('السعر مقارنة بالميزانية (مثبت)')).toBeInTheDocument()
  fireEvent.change(screen.getByRole('slider', { name: 'عرض الشارع' }), { target: { value: '1.5' } })
  fireEvent.click(screen.getByRole('button', { name: 'حفظ الأهمية' }))
  expect(save).toHaveBeenCalledWith({ weights: { street_width: 1.5 } })
})

it('unlocks and resets', () => {
  const save = vi.fn()
  render(<WeightsSection prefs={prefs as never} onSave={save} />)
  fireEvent.click(screen.getByRole('button', { name: 'إلغاء تثبيت السعر مقارنة بالميزانية' }))
  expect(save).toHaveBeenCalledWith({ unlock: ['price'] })
  fireEvent.click(screen.getByRole('button', { name: 'استعادة الافتراضي' }))
  expect(save).toHaveBeenCalledWith({ reset_weights: true })
})
```

`web/src/pages/settings/WeightsSection.tsx`:
```tsx
import { useState } from 'react'
import type { Preferences } from '../../api/types'
import { FACTOR_AR, type Factor } from '../../lib/factors'

interface Props { prefs: Preferences; onSave: (patch: Record<string, unknown>) => void }

export function WeightsSection({ prefs, onSave }: Props) {
  const [draft, setDraft] = useState<Record<string, number>>({})
  const changed = Object.keys(draft).length > 0
  return (
    <section className="space-y-3 rounded-2xl bg-white p-4 ring-1 ring-slate-200">
      <h2 className="font-semibold">أهمية العوامل</h2>
      <p className="text-sm text-slate-500">العوامل التي تعدّلها تُثبَّت ولا يغيّرها التعلّم التلقائي.</p>
      <ul className="space-y-3">
        {(Object.keys(FACTOR_AR) as Factor[]).map((f) => {
          const locked = prefs.locked_weights.includes(f)
          const value = draft[f] ?? prefs.weights[f] ?? 0
          return (
            <li key={f} className="flex items-center gap-3">
              <label htmlFor={`w-${f}`} className="w-40 shrink-0 text-sm" aria-label={locked ? `${FACTOR_AR[f]} (مثبت)` : undefined}>
                {FACTOR_AR[f]}
              </label>
              <input id={`w-${f}`} type="range" min={0} max={3} step={0.1} value={value} aria-label={FACTOR_AR[f]}
                     onChange={(e) => setDraft({ ...draft, [f]: Number(e.target.value) })} className="flex-1 accent-teal-700" />
              <span className="w-8 text-end text-sm tabular-nums">{value.toFixed(1)}</span>
              {locked ? (
                <button aria-label={`إلغاء تثبيت ${FACTOR_AR[f]}`} onClick={() => onSave({ unlock: [f] })} className="p-1">🔒</button>
              ) : <span className="w-7" />}
            </li>
          )
        })}
      </ul>
      <div className="flex gap-2">
        <button disabled={!changed} onClick={() => { onSave({ weights: draft }); setDraft({}) }}
                className="rounded-xl bg-brand px-4 py-2 font-semibold text-white disabled:opacity-40">حفظ الأهمية</button>
        <button onClick={() => onSave({ reset_weights: true })} className="rounded-xl bg-slate-100 px-4 py-2">استعادة الافتراضي</button>
      </div>
    </section>
  )
}
```

- [ ] **Step 3: Remaining sections**

Implement each section with the same card styling, a save button and a toast on success, and an inline error on 422 (show the server's `detail`):
- **PlacesSection:** for each kind (school, work, university, airport): a name input plus a `MapPicker`. "حفظ الأماكن" sends `PUT /api/places` with every kind that has a name and coordinates. After saving, show: "سيُعاد حساب المسافات عند اتصال جهاز التحديث" (distances will be recalculated once the update device is online).
- **MapPicker:** with `VITE_GOOGLE_MAPS_KEY`, show a 240px-high `<Map>` centered on the value (or Riyadh); `onClick` takes `ev.detail.latLng` and places an `<AdvancedMarker>`. Below it, always show a text input: "الصق إحداثيات أو رابط خرائط Google" (paste coordinates or a Google Maps link), parsed with `parseLatLng`, with error text `صيغة غير صحيحة` (invalid format).
- **FiltersSection:** property-type checkboxes using `PROPERTY_TYPE_AR`; a district tag input (Enter or "إضافة" adds a chip, ✕ removes); number inputs for price_max (ر.س), min_bedrooms, building_age_max and street_width_min; max-commute inputs per kind (minutes; empty means no limit); preferred facings as checkboxes (sent as `targets.preferred_facings`). Send `PUT /api/preferences {hard_filters, targets}`, with `null` for cleared numbers.
- **HistorySection:** the last 20 changes. Source icon (👤 user, 🤖 agent, 📈 learner), relative time, explanation, and a collapsible diff rendered as `FACTOR_AR`/field label: from → to.
- **StatusSection:** the Plan 1 status content plus `counts`, `last_scrape_at` per adapter, and a "استئناف" (resume) button on paused adapters that calls `POST /api/adapters/{source}/resume`.

- [ ] **Step 4: e2e**

Extend `web/e2e/fixtures.ts` so the mock handles `GET/PUT /api/preferences` (stateful), `GET/PUT /api/places`, `GET /api/preferences/changes`, and `POST /api/adapters/aqar/resume`.

`web/e2e/settings.spec.ts`:
```ts
import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test('edit filters and weights', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/settings')
  await page.getByLabel('أعلى سعر').fill('2000000')
  await page.getByLabel('حي').fill('النرجس')
  await page.getByRole('button', { name: 'إضافة' }).click()
  await page.getByRole('button', { name: 'حفظ الفلاتر' }).click()
  await expect(page.getByText('تم الحفظ')).toBeVisible()
  await page.getByRole('slider', { name: 'عرض الشارع' }).fill('2')
  await page.getByRole('button', { name: 'حفظ الأهمية' }).click()
  await expect(page.getByLabel('عرض الشارع (مثبت)')).toBeVisible()
})

test('set a place by pasting a google maps link', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/settings')
  const work = page.getByTestId('place-work')
  await work.getByLabel('الاسم').fill('المكتب')
  await work.getByPlaceholder('الصق إحداثيات أو رابط خرائط Google').fill('https://maps.google.com/?q=24.75,46.7')
  await page.getByRole('button', { name: 'حفظ الأماكن' }).click()
  await expect(page.getByText('سيُعاد حساب المسافات')).toBeVisible()
})
```

- [ ] **Step 5: Run `npm test && npx playwright test` and the RTL grep — expect PASS. Commit:**
```bash
git add web
git commit -m "feat: settings screen for places, filters, weights with locking, change history and system status"
```

---

### Task 5: Score explanation in detail + score-ranked feed

**Files:**
- Create: `web/src/components/ScoreBreakdown.tsx`, `web/src/components/ScoreBreakdown.test.tsx`
- Modify: `web/src/components/ListingDetailView.tsx` (render `<ScoreBreakdown>` under the commute chips; if `!passes_filters`, show filter reasons in an amber note), `backend/homefinder/server/routes/listings.py` (detail includes `passes_filters`, `filter_reasons`), `web/src/api/types.ts`

**Interfaces:**
- Produces: `<ScoreBreakdown breakdown={ScoreBreakdown | null}>`. It shows the 3 top positive contributions (green ＋, `FACTOR_AR` label) and the 3 most negative (red −). A "كل التفاصيل" (all details) toggle expands every contribution as a horizontal bar (width proportional to `value`) plus a "بيانات ناقصة:" (missing data) line listing missing factor labels. When `breakdown` is null, or its `total` is null, it shows "لا يوجد تقييم بعد" (no score yet).

- [ ] **Step 1: Failing test**

`web/src/components/ScoreBreakdown.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it } from 'vitest'
import { ScoreBreakdown } from './ScoreBreakdown'

const b = {
  total: 71, missing: ['street_width'],
  contributions: [
    { factor: 'price', value: 1, weight: 1, delta: 8.1 }, { factor: 'commute_work', value: 0.9, weight: 1, delta: 6.5 },
    { factor: 'yard', value: 1, weight: 0.3, delta: 2.4 }, { factor: 'bedrooms', value: 0.6, weight: 0.4, delta: 0.8 },
    { factor: 'building_age', value: 0, weight: 0.6, delta: -4.9 },
  ],
}

it('shows top pluses and minuses then expands', async () => {
  render(<ScoreBreakdown breakdown={b} />)
  expect(screen.getAllByTestId('plus').map((e) => e.textContent)).toEqual(['السعر مقارنة بالميزانية', 'القرب من العمل', 'حوش'])
  expect(screen.getAllByTestId('minus').map((e) => e.textContent)).toEqual(['حداثة البناء'])
  await userEvent.click(screen.getByRole('button', { name: 'كل التفاصيل' }))
  expect(screen.getByText(/بيانات ناقصة/)).toHaveTextContent('عرض الشارع')
})

it('handles no score', () => {
  render(<ScoreBreakdown breakdown={null} />)
  expect(screen.getByText('لا يوجد تقييم بعد')).toBeInTheDocument()
})
```

- [ ] **Step 2: Implement** to make the test pass (contributions with `delta > 0` sorted descending are pluses; `delta < 0` sorted ascending are minuses; 3 of each).

- [ ] **Step 3: Backend detail fields.** Add `passes_filters` and `filter_reasons` to `DETAIL_FIELDS`, and add an assertion to `test_detail_marks_seen_and_includes_sources`.

- [ ] **Step 4: Run all tests (backend + web unit + e2e) — expect PASS. Commit:**
```bash
git add backend web
git commit -m "feat: explainable score breakdown in listing detail"
```

## Plan 2 done when
All backend and web tests pass. With real data, changing a weight in Settings reorders the feed within seconds, even with the worker stopped.
