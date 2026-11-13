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
