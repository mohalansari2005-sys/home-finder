# Plan 4 — Learning From Reactions, Filter Suggestions, Comparison, Shortcuts

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rejects carry optional reasons. Every 10 reactions, the Mac fits a small logistic model and gently shifts the unlocked weights, with a readable Arabic explanation. Repeated reject reasons turn into suggested hard filters. The family can compare 2–4 listings, and desktop users get keyboard shortcuts.

**Architecture:** `homefinder/learner.py` (scikit-learn, worker only) is a pure function from feature rows and labels to new weights, plus a DB wrapper. `homefinder/suggestions.py` is pure and has no ML, so the server can compute suggestions without the Mac. The `react` endpoint enqueues a `learn` job when the threshold is reached.

**Tech Stack:** Adds `scikit-learn>=1.5`, `numpy` to the **worker** extra only.

**Spec:** `docs/superpowers/specs/2026-11-13-home-finder-design.md` §3.4, §3.7 (compare, shortcuts), §5.4

## Global Constraints

All constraints in `2026-11-13-00-overview.md`. Plans 1–3 must be complete and green. **The server image must not import sklearn**: `homefinder/server/**` must never import `homefinder.learner`. Add `tests/test_import_boundaries.py` to enforce this.

## Review Focus

1. **Only bookmarks, no rejects** (a single label class): the learner skips with `{"skipped": "need both classes"}` and doesn't crash. Pinned in `test_learner_needs_both_classes`.
2. **Locked weights never move**, even when the data strongly disagrees. Pinned in `test_locked_weights_untouched`.
3. **A weight at 0 can still grow** once the data supports it (the step cap uses `max(0.2·w, 0.05)`). Pinned in `test_zero_weight_can_grow`.
4. **A dismissed suggestion doesn't come back** unless 5 *new* rejects with that reason arrive after the dismissal. Pinned in `test_dismissed_suggestion_stays_hidden`.
5. **A keyboard shortcut while typing** in an input or textarea (e.g. typing "b" in the chat) must not bookmark anything. Pinned in the e2e test `shortcuts ignore typing`.

---

### Task 1: Learner (pure + job)

**Files:**
- Create: `backend/homefinder/learner.py`, `backend/tests/test_learner.py`, `backend/tests/test_import_boundaries.py`, migration `0004_learned_through`
- Modify: `backend/pyproject.toml` (worker extra), `backend/homefinder/models.py` (`Preferences.learned_through_reaction_id: int = 0`), `backend/homefinder/worker/handlers.py` (register `learn`)

**Interfaces:**
- Produces:
  - `learner.LABEL_RULES`: bookmark → (1, weight 1); reject → (0, 1); visit_rating 4–5 → (1, 3); visit_rating 1–2 → (0, 3); visit_rating 3 → ignored
  - `learner.build_dataset(rows: list[tuple[dict[str, float | None], str, int | None]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]` (X with missing values filled with 0.5, y, sample_weight, factor order = `scoring.FACTORS`)
  - `learner.fit_weights(X, y, sw, factors, current: dict, locked: list[str]) -> dict[str, float]`
  - `learner.explain(old: dict, new: dict) -> str` (Arabic; names the biggest increase and the biggest decrease)
  - `learner.run_learn(s) -> dict` (`{"updated": [...], "explanation": str}` or `{"skipped": reason}`). It writes the weights, a `PreferenceChange(source="learner")`, `learned_through_reaction_id`, and rescores everything.
  - Job `learn` (`{}`).

- [ ] **Step 1: Failing tests**

`backend/tests/test_learner.py`:
```python
import numpy as np
import pytest

from homefinder.learner import build_dataset, explain, fit_weights, run_learn
from homefinder.models import Listing, PreferenceChange, Preferences, Reaction
from homefinder.scoring import DEFAULT_WEIGHTS, FACTORS


def synthetic(n=40, seed=0):
    """Family loves wide streets; nothing else matters."""
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(n):
        v = {f: float(rng.random()) for f in FACTORS}
        kind = "bookmark" if v["street_width"] > 0.5 else "reject"
        rows.append((v, kind, None))
    return rows


def test_build_dataset_labels_and_weights():
    rows = [({"price": 1.0}, "bookmark", None), ({"price": None}, "reject", None),
            ({"price": 0.2}, "visit_rating", 5), ({"price": 0.3}, "visit_rating", 3)]
    X, y, sw, factors = build_dataset(rows)
    assert X.shape == (3, len(FACTORS)) and list(y) == [1, 0, 1] and list(sw) == [1, 1, 3]
    assert X[1, factors.index("price")] == 0.5


def test_weight_moves_toward_signal_and_is_capped():
    X, y, sw, f = build_dataset(synthetic())
    new = fit_weights(X, y, sw, f, dict(DEFAULT_WEIGHTS), locked=[])
    old = DEFAULT_WEIGHTS["street_width"]
    assert new["street_width"] > old
    assert new["street_width"] <= old + max(0.2 * old, 0.05) + 1e-9
    for k in FACTORS:
        assert abs(new[k] - DEFAULT_WEIGHTS[k]) <= max(0.2 * DEFAULT_WEIGHTS[k], 0.05) + 1e-9


def test_locked_weights_untouched():
    X, y, sw, f = build_dataset(synthetic())
    new = fit_weights(X, y, sw, f, dict(DEFAULT_WEIGHTS), locked=["street_width", "price"])
    assert new["street_width"] == DEFAULT_WEIGHTS["street_width"] and new["price"] == DEFAULT_WEIGHTS["price"]


def test_zero_weight_can_grow():
    X, y, sw, f = build_dataset(synthetic())
    cur = dict(DEFAULT_WEIGHTS, street_width=0.0)
    assert fit_weights(X, y, sw, f, cur, locked=[])["street_width"] == pytest.approx(0.05)


def test_explain_arabic():
    old = dict(DEFAULT_WEIGHTS)
    new = dict(old, street_width=old["street_width"] + 0.1, yard=old["yard"] - 0.06)
    txt = explain(old, new)
    assert "عرض الشارع" in txt and "حوش" in txt


def test_learner_needs_both_classes(db):
    for _ in range(12):
        l = Listing(price=1_000_000); db.add(l); db.flush(); db.add(Reaction(listing_id=l.id, kind="bookmark"))
    db.commit()
    assert run_learn(db) == {"skipped": "need both classes"}


def test_run_learn_end_to_end(db):
    rng = np.random.default_rng(1)
    for i in range(30):
        w = float(rng.uniform(8, 30))
        l = Listing(price=1_000_000, street_width_m=w); db.add(l); db.flush()
        db.add(Reaction(listing_id=l.id, kind="bookmark" if w > 18 else "reject"))
    db.commit()
    out = run_learn(db); db.commit()
    assert "street_width" in out["updated"]
    p = db.get(Preferences, 1)
    assert p.weights["street_width"] > DEFAULT_WEIGHTS["street_width"]
    assert p.learned_through_reaction_id == db.query(Reaction).order_by(Reaction.id.desc()).first().id
    assert db.query(PreferenceChange).filter_by(source="learner").count() == 1
```

`backend/tests/test_import_boundaries.py`:
```python
import ast
from pathlib import Path

SERVER = Path(__file__).parents[1] / "homefinder" / "server"
FORBIDDEN = ("homefinder.learner", "sklearn", "PIL", "imagehash", "playwright")


def test_server_does_not_import_worker_only_libs():
    for py in SERVER.rglob("*.py"):
        tree = ast.parse(py.read_text("utf-8"))
        for node in ast.walk(tree):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else \
                    [node.module or ""] if isinstance(node, ast.ImportFrom) else []
            for n in names:
                assert not n.startswith(FORBIDDEN), f"{py} imports {n}"
```
Caveat: `server/agent/fallback_search.py` imports `homefinder.worker.sources.aqar`, which imports `aqar_transport`. That module only imports `playwright` lazily inside `PlaywrightTransport._ensure`, which is allowed. `homefinder.dedupe` imports `imagehash` and is **only** used by the worker; keep it out of `server/`.

- [ ] **Step 2: Implement learner.py**

```python
import numpy as np
from sklearn.linear_model import LogisticRegression
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homefinder import prefs as prefs_mod
from homefinder.models import Listing, Reaction
from homefinder.rescore import record_change, rescore_all, snapshot
from homefinder.scoring import FACTORS, effective_weights, factor_values

MIN_EACH_CLASS = 5
BLEND = 0.3
FACTOR_AR = {
    "commute_school": "القرب من المدرسة", "commute_work": "القرب من العمل", "commute_university": "القرب من الجامعة",
    "commute_airport": "القرب من المطار", "price": "السعر", "built_area": "مساحة البناء", "land_area": "مساحة الأرض",
    "building_age": "حداثة البناء", "street_width": "عرض الشارع", "facing": "اتجاه الواجهة", "street_count": "عدد الشوارع",
    "deed_type": "نوع الصك", "bedrooms": "عدد الغرف", "bathrooms": "دورات المياه", "maid_room": "غرفة الخادمة",
    "driver_room": "غرفة السائق", "yard": "حوش", "elevator": "المصعد",
}


def _label(kind: str, rating: int | None) -> tuple[int, float] | None:
    if kind == "bookmark":
        return 1, 1.0
    if kind == "reject":
        return 0, 1.0
    if kind == "visit_rating" and rating is not None:
        return (1, 3.0) if rating >= 4 else (0, 3.0) if rating <= 2 else None
    return None


def build_dataset(rows):
    X, y, sw = [], [], []
    for values, kind, rating in rows:
        lab = _label(kind, rating)
        if lab is None:
            continue
        X.append([0.5 if values.get(f) is None else values[f] for f in FACTORS])
        y.append(lab[0]); sw.append(lab[1])
    return np.array(X, dtype=float).reshape(-1, len(FACTORS)), np.array(y), np.array(sw), list(FACTORS)


def fit_weights(X, y, sw, factors, current: dict, locked: list[str]) -> dict[str, float]:
    cur = effective_weights(current)
    model = LogisticRegression(C=1.0, max_iter=1000)
    model.fit(X, y, sample_weight=sw)
    coef = dict(zip(factors, model.coef_[0]))
    free = [f for f in factors if f not in locked]
    pos = {f: max(0.0, coef[f]) for f in free}
    budget = sum(cur[f] for f in free)
    total = sum(pos.values())
    target = {f: (pos[f] / total * budget if total > 0 else cur[f]) for f in free}
    new = dict(cur)
    for f in free:
        step = BLEND * (target[f] - cur[f])
        cap = max(0.2 * cur[f], 0.05)
        new[f] = round(min(3.0, max(0.0, cur[f] + max(-cap, min(cap, step)))), 3)
    return new


def explain(old: dict, new: dict) -> str:
    deltas = {f: new[f] - old.get(f, 0) for f in new}
    up = max(deltas, key=deltas.get)
    down = min(deltas, key=deltas.get)
    parts = []
    if deltas[up] > 0.01:
        parts.append(f"زادت أهمية {FACTOR_AR[up]}")
    if deltas[down] < -0.01:
        parts.append(f"قلّت أهمية {FACTOR_AR[down]}")
    return ("، ".join(parts) + " بناءً على تفاعلكم مع العقارات.") if parts else "لا تغييرات تُذكر."


def run_learn(s: Session) -> dict:
    p = prefs_mod.get_or_create(s)
    reacts = list(s.execute(select(Reaction, Listing).join(Listing, Listing.id == Reaction.listing_id)
                            .where(Reaction.kind.in_(["bookmark", "reject", "visit_rating"]))
                            .order_by(Reaction.id)).all())
    # latest reaction per listing wins (a later reject overrides an earlier bookmark)
    latest: dict[int, tuple] = {}
    for r, l in reacts:
        latest[l.id] = (factor_values(l, p.hard_filters, p.targets), r.kind, r.rating)
    X, y, sw, factors = build_dataset(list(latest.values()))
    if len(y) == 0 or min((y == 1).sum(), (y == 0).sum()) < MIN_EACH_CLASS:
        return {"skipped": "need both classes"}
    before = snapshot(p)
    old = effective_weights(p.weights)
    new = fit_weights(X, y, sw, factors, p.weights, p.locked_weights)
    changed = [f for f in factors if abs(new[f] - old[f]) > 1e-6]
    p.weights = {f: new[f] for f in factors if f in p.weights or f in changed}
    p.learned_through_reaction_id = max(r.id for r, _ in reacts)
    text = explain(old, new)
    record_change(s, "learner", before, snapshot(p), text)
    rescore_all(s)
    return {"updated": changed, "explanation": text}
```
Register it in handlers: `HANDLERS["learn"] = lambda deps, p: _with_session(deps, run_learn)`, where `_with_session` opens `deps.session_factory()` and calls the function with it. Import `run_learn` inside the lambda so the module is only imported when the job runs.

- [ ] **Step 3: Run — expect PASS. Commit** `feat: logistic-regression weight learner with caps, locks and arabic explanations`.

---

### Task 2: Reject reasons, learn trigger, filter suggestions

**Files:**
- Create: `backend/homefinder/suggestions.py`, `backend/tests/test_suggestions.py`, `backend/homefinder/server/routes/suggestions.py`, `backend/tests/server/test_suggestions_api.py`
- Modify: `backend/homefinder/server/routes/listings.py` (`react` validates `reason_code` and enqueues `learn`), `backend/homefinder/server/app.py`, `backend/homefinder/server/agent/tools.py` (+2 tools), `backend/tests/agent/test_tools.py`

**Interfaces:**
- Produces:
  - `REASON_CODES = ["too_old", "narrow_street", "bad_layout", "overpriced", "far", "other"]`. The `react` endpoint rejects any other `reason_code` with 422.
  - Learn trigger: after a reaction, `count(reactions where id > prefs.learned_through_reaction_id and kind in (bookmark, reject, visit_rating)) >= 10` → `jobs.enqueue(s, "learn", {}, dedupe_key="learn")`.
  - `suggestions.compute(rejects: list[tuple[reason_code, Listing-like, reaction_id]], hard_filters, dismissed: list[dict]) -> list[dict]`. Each suggestion is `{"code": str, "reason": str, "count": int, "patch": {"hard_filters": {...}}, "text": str}` (Arabic text).
    - `too_old` → `building_age_max = max(0, median(rejected ages) - 1)`
    - `narrow_street` → `street_width_min = median(rejected widths) + 1`
    - `overpriced` → `price_max = round(0.9 * median(rejected prices), -4)`, only if lower than the current price_max
    - `far` → `max_commute.work = median(rejected work commutes) - 5`
    - `bad_layout` and `other` → no suggestion
    - Rule: ≥ 5 of the last 20 rejects share the reason, the needed values are known for ≥ 3 of them, and the suggestion isn't dismissed (a dismissal `{code, at_reaction_id}` hides it until 5 rejects with that reason have `id > at_reaction_id`).
  - `GET /api/suggestions` → list; `POST /api/suggestions/{code}/apply` → applies the patch through `apply_prefs_patch(s, PrefsPatch(**patch), "user", text)`, then rescores in the background; `POST /api/suggestions/{code}/dismiss` → 204 (stores the dismissal in `targets.dismissed_suggestions`).
  - Agent tools `get_filter_suggestions()` and `apply_filter_suggestion(code: str)`.

- [ ] **Step 1: Failing tests**

`backend/tests/test_suggestions.py`:
```python
from types import SimpleNamespace as N

from homefinder.suggestions import compute


def rej(reason, i, **kw):
    base = dict(building_age_years=None, street_width_m=None, price=None, commutes={})
    base.update(kw)
    return (reason, N(**base), i)


def test_too_old_suggestion():
    rs = [rej("too_old", i, building_age_years=a) for i, a in enumerate([18, 20, 22, 25, 30], start=1)]
    [s] = compute(rs, {}, [])
    assert s["code"] == "too_old" and s["patch"] == {"hard_filters": {"building_age_max": 21}} and s["count"] == 5


def test_needs_five_and_known_values():
    rs = [rej("too_old", i, building_age_years=20) for i in range(1, 5)]
    assert compute(rs, {}, []) == []
    rs = [rej("narrow_street", i) for i in range(1, 7)]  # widths unknown
    assert compute(rs, {}, []) == []


def test_overpriced_only_if_lower():
    rs = [rej("overpriced", i, price=2_000_000) for i in range(1, 6)]
    assert compute(rs, {"price_max": 1_500_000}, []) == []
    [s] = compute(rs, {"price_max": 2_500_000}, [])
    assert s["patch"]["hard_filters"]["price_max"] == 1_800_000


def test_dismissed_suggestion_stays_hidden():
    rs = [rej("too_old", i, building_age_years=25) for i in range(1, 6)]
    dismissed = [{"code": "too_old", "at_reaction_id": 5}]
    assert compute(rs, {}, dismissed) == []
    more = rs + [rej("too_old", i, building_age_years=25) for i in range(6, 11)]
    assert [s["code"] for s in compute(more, {}, dismissed)] == ["too_old"]


def test_only_last_20_considered():
    old = [rej("too_old", i, building_age_years=25) for i in range(1, 6)]
    recent = [rej("other", i) for i in range(6, 26)]
    assert compute(old + recent, {}, []) == []
```

`backend/tests/server/test_suggestions_api.py`:
```python
from homefinder.models import Job, Listing, Preferences


def _reject(family, db, age, reason="too_old"):
    l = Listing(building_age_years=age); db.add(l); db.commit()
    return family.post(f"/api/listings/{l.id}/react", json={"kind": "reject", "reason_code": reason})


def test_invalid_reason_code(db, family):
    assert _reject(family, db, 10, reason="ugly").status_code == 422


def test_learn_enqueued_after_10(db, family):
    for i in range(9):
        _reject(family, db, 20)
    assert db.query(Job).filter_by(type="learn").count() == 0
    _reject(family, db, 20)
    assert db.query(Job).filter_by(type="learn").count() == 1


def test_suggestion_apply_and_dismiss(db, family):
    for a in [18, 20, 22, 25, 30]:
        _reject(family, db, a)
    [s] = family.get("/api/suggestions").json()
    assert s["code"] == "too_old"
    assert family.post("/api/suggestions/too_old/apply").status_code == 200
    db.expire_all()
    assert db.get(Preferences, 1).hard_filters["building_age_max"] == 21
    assert family.get("/api/suggestions").json() == []  # now satisfied: rejected ones exceed filter but suggestion equals current
    assert family.post("/api/suggestions/narrow_street/dismiss").status_code == 204
```
Rule needed for the second-to-last assertion: `compute` drops a suggestion whose patch values already equal the current hard filters.

- [ ] **Step 2: Implement** suggestions.py (pure; uses `statistics.median`; Arabic texts such as `"رفضتم 5 عقارات لأنها قديمة. هل نستبعد العقارات الأقدم من 21 سنة؟"`), the route file, the `react` changes, and the two agent tools. Then update `test_tool_names` to include the new tools.

- [ ] **Step 3: Run backend suite — expect PASS. Commit** `feat: reject reasons, learn trigger, filter suggestions api and agent tools`.

---

### Task 3: Reject-reason sheet, suggestion banner, learning history

**Files:**
- Create: `web/src/components/RejectReasonSheet.tsx`, `RejectReasonSheet.test.tsx`, `web/src/components/SuggestionBanner.tsx`
- Modify: `web/src/components/FeedList.tsx`, `ListingDetailView.tsx` (reject opens the sheet), `web/src/pages/FeedPage.tsx` (banner above the list), `web/src/api/hooks.ts` (`useSuggestions`, `useApplySuggestion`, `useDismissSuggestion`; `useReact` accepts `reason_code`/`note`), `web/src/pages/settings/HistorySection.tsx` (📈 learner entries already render; add the heading "ما تعلّمه التطبيق" for learner entries)

**Interfaces:**
- `<RejectReasonSheet open listingTitle onSubmit({reason_code?, note?}) onCancel>`:
  - phone: a bottom sheet; tablet/desktop: a centered dialog.
  - Contents: chips for each `REASON_CODES` entry (Arabic labels from `REASON_AR`), an optional note textarea, and the buttons "استبعاد" (reject; submits with the selected reason) and "تخطي" (skip; submits without a reason).
  - Accessibility: `role="dialog"` and `aria-modal="true"`; Escape cancels; focus is trapped inside.
- The listing is hidden optimistically right after submit.
- `<SuggestionBanner>`: for each suggestion, an amber card with the Arabic `text` and the buttons "تطبيق" (apply) and "لا شكراً" (no thanks).

- [ ] **Step 1: Failing test**

```tsx
// RejectReasonSheet.test.tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { RejectReasonSheet } from './RejectReasonSheet'

it('submits chosen reason and note', async () => {
  const onSubmit = vi.fn()
  render(<RejectReasonSheet open listingTitle="فيلا" onSubmit={onSubmit} onCancel={() => {}} />)
  await userEvent.click(screen.getByRole('button', { name: 'قديم' }))
  await userEvent.type(screen.getByLabelText('ملاحظة (اختياري)'), 'المطبخ صغير')
  await userEvent.click(screen.getByRole('button', { name: 'استبعاد' }))
  expect(onSubmit).toHaveBeenCalledWith({ reason_code: 'too_old', note: 'المطبخ صغير' })
})

it('skip submits without reason; escape cancels', async () => {
  const onSubmit = vi.fn(), onCancel = vi.fn()
  render(<RejectReasonSheet open listingTitle="فيلا" onSubmit={onSubmit} onCancel={onCancel} />)
  await userEvent.click(screen.getByRole('button', { name: 'تخطي' }))
  expect(onSubmit).toHaveBeenCalledWith({})
  await userEvent.keyboard('{Escape}')
  expect(onCancel).toHaveBeenCalled()
})
```
In `REASON_AR`, `too_old` must be `'قديم'` (it already is).

- [ ] **Step 2: Implement, wire into the feed and detail views, update e2e fixtures** (the mock answers `/api/suggestions` with one suggestion). Add an e2e test: reject → choose a reason → the card disappears; the banner's "تطبيق" (apply) → the banner disappears.

- [ ] **Step 3: Run all web tests. Commit** `feat: reject reason sheet, filter suggestion banner`.

---

### Task 4: Comparison view and desktop keyboard shortcuts

**Files:**
- Create: `backend/tests/server/test_compare_api.py`; `web/src/pages/ComparePage.tsx`, `web/src/components/CompareBar.tsx`, `web/src/lib/compare.ts`, `web/src/lib/compare.test.ts`, `web/src/lib/useShortcuts.ts`, `web/e2e/compare.spec.ts`
- Modify: `backend/homefinder/server/routes/listings.py` (`GET /api/compare?ids=1,2,3`), `web/src/components/ListingCard.tsx` (a "قارن" (compare) toggle button when the `compareMode` prop is set), `web/src/pages/FeedPage.tsx` (compare mode: the selection is kept in `?compare=1,2`; `CompareBar` is pinned to the bottom and shows "قارن (n)"; shortcuts on desktop), `web/src/App.tsx` (route `/compare`)

**Interfaces:**
- `GET /api/compare?ids=` → `ListingDetail[]` in the order requested, max 4. Doesn't change `family_status`. Unknown ids are skipped. 422 if fewer than 2 or more than 4 valid ids are given.
- `compare.ts`:
  - `COMPARE_ROWS: {key, label, better: 'higher'|'lower'|null, fmt}[]`, covering price (lower is better), score (higher), commutes ×4 (lower), built_area (higher), land_area (higher), building_age_years (lower), street_width_m (higher), bedrooms (higher), bathrooms (higher), facing (null), deed_type (null), has_maid_room / has_driver_room / has_yard / has_elevator (null)
  - `bestIndex(values: (number|null)[], better) -> number | null`: index of the best value, ignoring nulls; null when tied or when fewer than 2 values are known
- `maxCompare(bp)`: phone 2, tablet 3, desktop 4. Selecting beyond the limit shows a toast "الحد الأقصى للمقارنة {n}" (max comparison limit).
- ComparePage layouts:
  - phone: two columns side by side, with sticky headers and a swipe-to-scroll body. A select per column swaps which of the chosen listings is shown.
  - tablet: 2–3 columns.
  - desktop: a table with row labels on the start side and listings as columns.
  - On all layouts: the best cell per row is highlighted (emerald background) and missing values show "غير مذكور" in amber.
- `useShortcuts({onBookmark, onReject, onNext, onPrev, enabled})`: listens to `keydown` on `window`. It ignores events whose target is an `input`, `textarea`, `select` or `[contenteditable]`, and any event with a modifier key held. Keys: `b`/`B` bookmark, `x`/`X` reject (opens the reason sheet), `ArrowLeft` next and `ArrowRight` previous (RTL reading order).
- FeedPage on desktop: the selection moves through the loaded items. A small hint "اختصارات: B حفظ · X استبعاد · ←/→ تنقل" (shortcuts: B save · X reject · ←/→ move) appears under the view tabs.

- [ ] **Step 1: Failing tests**

`backend/tests/server/test_compare_api.py`:
```python
from homefinder.models import Listing


def test_compare_orders_and_validates(db, family):
    ids = []
    for p in (1_000_000, 2_000_000, 3_000_000):
        l = Listing(price=p); db.add(l); db.flush(); ids.append(l.id)
    db.commit()
    out = family.get(f"/api/compare?ids={ids[2]},{ids[0]}").json()
    assert [x["id"] for x in out] == [ids[2], ids[0]] and out[0]["family_status"] == "new"
    assert family.get(f"/api/compare?ids={ids[0]}").status_code == 422
    assert family.get(f"/api/compare?ids={ids[0]},999999").status_code == 422
```

`web/src/lib/compare.test.ts`:
```ts
import { expect, it } from 'vitest'
import { bestIndex } from './compare'

it('picks best by direction ignoring nulls and ties', () => {
  expect(bestIndex([3, 1, 2], 'lower')).toBe(1)
  expect(bestIndex([3, null, 5], 'higher')).toBe(2)
  expect(bestIndex([2, 2], 'higher')).toBeNull()
  expect(bestIndex([null, 4], 'higher')).toBeNull()
  expect(bestIndex([1, 2], null)).toBeNull()
})
```

`web/e2e/compare.spec.ts` (extend the fixtures to serve `/api/compare`):
```ts
import { expect, test } from '@playwright/test'
import { mockApi } from './fixtures'

test('compare two listings', async ({ page }) => {
  await mockApi(page, { loggedIn: true })
  await page.goto('/?view=bookmarked')
  await page.getByRole('button', { name: 'وضع المقارنة' }).click()
  await page.getByRole('article').filter({ hasText: 'فيلا 1' }).getByRole('button', { name: 'قارن' }).click()
  await page.getByRole('article').filter({ hasText: 'فيلا 2' }).getByRole('button', { name: 'قارن' }).click()
  await page.getByRole('button', { name: 'قارن (2)' }).click()
  await expect(page).toHaveURL(/\/compare\?ids=1,2/)
  await expect(page.getByTestId('best-cell').first()).toBeVisible()
})

test('shortcuts ignore typing', async ({ page }, info) => {
  test.skip(info.project.name !== 'desktop')
  await mockApi(page, { loggedIn: true })
  await page.goto('/')
  await page.getByRole('article').filter({ hasText: 'فيلا 1' }).click()
  await page.getByRole('textbox').first().focus()   // docked chat input
  await page.keyboard.press('b')
  await expect(page.getByRole('article').filter({ hasText: 'فيلا 1' }).getByRole('button', { name: 'حفظ' })).toBeVisible()
  await page.locator('body').click({ position: { x: 5, y: 5 } })
  await page.keyboard.press('b')
  await expect(page.getByRole('article').filter({ hasText: 'فيلا 1' }).getByRole('button', { name: 'محفوظ' })).toBeVisible()
})
```

- [ ] **Step 2: Implement** the endpoint, compare.ts, CompareBar, ComparePage, useShortcuts and FeedPage wiring until all tests pass.

- [ ] **Step 3: Run all tests (backend, web unit, e2e ×3) + RTL grep. Commit** `feat: listing comparison (2/3/4 by device) and desktop keyboard shortcuts`.

## Plan 4 done when
All suites pass. After 10+ reactions with the worker running, Settings → سجل التغييرات (change history) shows a 📈 learner entry with an Arabic explanation, and the feed order changes accordingly.
