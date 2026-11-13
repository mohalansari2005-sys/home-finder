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


def _dataset(s: Session):
    p = prefs_mod.get_or_create(s)
    reacts = list(s.execute(select(Reaction, Listing).join(Listing, Listing.id == Reaction.listing_id)
                            .where(Reaction.kind.in_(["bookmark", "reject", "unreject", "visit_rating"]))
                            .order_by(Reaction.id)).all())
    # latest reaction per listing wins (a later reject overrides an earlier bookmark)
    latest: dict[int, tuple] = {}
    for r, l in reacts:
        if r.kind == "unreject":  # taking a reject back removes the label
            latest.pop(l.id, None)
            continue
        latest[l.id] = (factor_values(l, p.hard_filters, p.targets), r.kind, r.rating)
    return (*build_dataset(list(latest.values())), reacts)


def run_learn(s: Session) -> dict:
    p = prefs_mod.get_or_create(s)
    X, y, sw, factors, reacts = _dataset(s)
    if len(y) == 0 or min((y == 1).sum(), (y == 0).sum()) < MIN_EACH_CLASS:
        if reacts:  # remember the attempt so the server doesn't re-trigger on every later reaction
            p.learn_attempted_through_reaction_id = max(r.id for r, _ in reacts)
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
