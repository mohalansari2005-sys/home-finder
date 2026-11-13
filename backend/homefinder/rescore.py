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
