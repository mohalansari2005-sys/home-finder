import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder.models import DistrictDriveCache, Listing
from homefinder.textnorm import normalize_district

log = logging.getLogger(__name__)
RIYADH = ZoneInfo("Asia/Riyadh")
CANDIDATE_KM = 6.0  # only district pairs this close are worth a TomTom call
MERGE_MINUTES = 10
FALLBACK_KM = 3.0  # without drive times, merge on distance alone
CACHE_TTL = timedelta(days=90)
NO_DISTRICT = "بدون حي"


@dataclass
class Group:
    key: str
    districts: list[str]
    listing_ids: list[int]
    count: int
    avg_score: float | None
    centroid: tuple[float, float]


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(radians, (*a, *b))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * 6371 * asin(sqrt(h))


def next_saturday_16(now: datetime | None = None) -> datetime:
    local = (now or datetime.now(UTC)).astimezone(RIYADH)
    d = local.date() + timedelta(days=(5 - local.weekday()) % 7)
    cand = datetime.combine(d, time(16), tzinfo=RIYADH)
    if cand <= local + timedelta(minutes=10):
        cand += timedelta(days=7)
    return cand.astimezone(UTC)


def _display(raw: str) -> str:
    return re.sub(r"^حي\s+", "", raw.strip())


def _centroid(rows: list[Listing]) -> tuple[float, float]:
    return sum(l.lat for l in rows) / len(rows), sum(l.lng for l in rows) / len(rows)


def _drive_minutes(s: Session, maps, pairs: list[tuple[str, str]], cents: dict[str, tuple[float, float]]) -> dict:
    """{(a, b): minutes|None} for pairs (a < b) from the cache or one TomTom call per origin district.
    A TomTom failure leaves the pair out of the result (callers fall back to distance); it is never cached."""
    out: dict[tuple[str, str], int | None] = {}
    fresh_after = datetime.now(UTC) - CACHE_TTL
    todo: dict[str, list[str]] = {}
    for a, b in pairs:
        row = s.get(DistrictDriveCache, (a, b))
        if row is not None and row.computed_at >= fresh_after:
            out[(a, b)] = row.minutes
        else:
            todo.setdefault(a, []).append(b)
    if maps is None:
        return out
    dep = next_saturday_16()
    for a, bs in todo.items():
        try:
            mins = maps.drive_minutes(cents[a], [cents[b] for b in bs], dep)
        except Exception as e:  # noqa: BLE001 — quota or outage: group by distance instead
            log.warning("district drive times unavailable: %s", e)
            continue
        for b, m in zip(bs, mins):
            s.merge(DistrictDriveCache(a=a, b=b, minutes=m, computed_at=datetime.now(UTC)))
            out[(a, b)] = m
    s.flush()
    return out


def group_bookmarks(s: Session, maps) -> tuple[list[Group], list[int]]:
    rows = list(s.scalars(select(Listing).where(
        Listing.family_status == "bookmarked", Listing.merged_into_id.is_(None), Listing.status == "active")
        .order_by(Listing.id)))
    no_coords = [l.id for l in rows if l.lat is None or l.lng is None]
    rows = [l for l in rows if l.lat is not None and l.lng is not None]

    by_district: dict[str, list[Listing]] = {}
    names: dict[str, str] = {}
    solo: list[Listing] = []
    for l in rows:
        k = normalize_district(l.district)
        if not k:
            solo.append(l)
            continue
        by_district.setdefault(k, []).append(l)
        names.setdefault(k, _display(l.district))

    cents = {k: _centroid(v) for k, v in by_district.items()}
    keys = sorted(by_district)
    close = [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:]
             if haversine_km(cents[a], cents[b]) <= CANDIDATE_KM]
    minutes = _drive_minutes(s, maps, close, cents) if close else {}

    parent = {k: k for k in keys}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b in close:
        if (a, b) in minutes:
            merge = minutes[(a, b)] is not None and minutes[(a, b)] <= MERGE_MINUTES
        else:
            merge = haversine_km(cents[a], cents[b]) <= FALLBACK_KM
        if merge:
            parent[find(b)] = find(a)

    clusters: dict[str, list[str]] = {}
    for k in keys:
        clusters.setdefault(find(k), []).append(k)

    def build(key: str, display: list[str], ls: list[Listing]) -> Group:
        scores = [l.score for l in ls if l.score is not None]
        return Group(key=key, districts=display, listing_ids=[l.id for l in ls], count=len(ls),
                     avg_score=sum(scores) / len(scores) if scores else None, centroid=_centroid(ls))

    groups = []
    for members in clusters.values():
        ls = sorted((l for k in members for l in by_district[k]), key=lambda l: l.id)
        groups.append(build("+".join(sorted(members)), [names[k] for k in sorted(members)], ls))
    groups += [build(f"listing:{l.id}", [NO_DISTRICT], [l]) for l in solo]
    groups.sort(key=lambda g: (-(g.count * (g.avg_score if g.avg_score is not None else 50)), g.key))
    return groups, no_coords
