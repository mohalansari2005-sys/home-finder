"""Filter suggestions from repeated reject reasons. Pure functions, no ML: the server can compute these without the Mac."""
from statistics import median

REASON_CODES = ["too_old", "narrow_street", "bad_layout", "overpriced", "far", "other"]
WINDOW = 20
MIN_SHARE = 5
MIN_KNOWN = 3


def _values(reason: str, rows: list) -> list[float]:
    if reason == "too_old":
        vals = [l.building_age_years for l in rows]
    elif reason == "narrow_street":
        vals = [l.street_width_m for l in rows]
    elif reason == "overpriced":
        vals = [l.price for l in rows]
    elif reason == "far":
        vals = [(l.commutes or {}).get("work") for l in rows]
    else:
        vals = []
    return [v for v in vals if v is not None]


def _build(reason: str, med: float, hf: dict, n: int) -> tuple[dict, str] | None:
    """(hard_filters patch, Arabic text), or None when the filter is already at least as strict."""
    if reason == "too_old":
        v = min(80, max(0, int(med) - 1))
        cur = hf.get("building_age_max")
        if cur is not None and cur <= v:
            return None
        return {"building_age_max": v}, f"رفضتم {n} عقارات لأنها قديمة. هل نستبعد العقارات الأقدم من {v} سنة؟"
    if reason == "narrow_street":
        v = round(min(100.0, max(4.0, med + 1)), 1)
        cur = hf.get("street_width_min")
        if cur is not None and cur >= v:
            return None
        return {"street_width_min": v}, f"رفضتم {n} عقارات لأن الشارع ضيق. هل نشترط عرض شارع {v:g} متر على الأقل؟"
    if reason == "overpriced":
        v = int(round(0.9 * med, -4))
        cur = hf.get("price_max")
        if v < 100_000 or (cur is not None and cur <= v):
            return None
        return {"price_max": v}, f"رفضتم {n} عقارات لأن سعرها مرتفع. هل نحدد الحد الأعلى للسعر بـ {v:,} ريال؟"
    if reason == "far":
        v = int(min(180, max(5, round(med) - 5)))
        commute = dict(hf.get("max_commute") or {})
        if commute.get("work") is not None and commute["work"] <= v:
            return None
        commute["work"] = v
        return {"max_commute": commute}, f"رفضتم {n} عقارات لأنها بعيدة. هل نحدد أقصى مدة للوصول إلى العمل بـ {v} دقيقة؟"
    return None


def compute(rejects: list[tuple], hard_filters: dict, dismissed: list[dict]) -> list[dict]:
    """rejects: (reason_code, listing-like, reaction_id). Only the last WINDOW rejects count."""
    recent = sorted(rejects, key=lambda r: r[2])[-WINDOW:]
    hf = hard_filters or {}
    out = []
    for reason in REASON_CODES:
        mine = [(l, rid) for code, l, rid in recent if code == reason]
        if len(mine) < MIN_SHARE:
            continue
        at = max((d.get("at_reaction_id", 0) for d in dismissed or [] if d.get("code") == reason), default=None)
        if at is not None and sum(1 for _, rid in mine if rid > at) < MIN_SHARE:
            continue
        known = _values(reason, [l for l, _ in mine])
        if len(known) < MIN_KNOWN:
            continue
        built = _build(reason, median(known), hf, len(mine))
        if built is None:
            continue
        patch, text = built
        out.append({"code": reason, "reason": reason, "count": len(mine),
                    "patch": {"hard_filters": patch}, "text": text})
    return out
