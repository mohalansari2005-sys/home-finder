from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder.models import CommuteCache, Listing, Place

RIYADH = ZoneInfo("Asia/Riyadh")
WORKDAYS = {6, 0, 1, 2, 3}  # Python weekday(): Sun=6, Mon=0 .. Thu=3
DEPARTURE = {"school": time(7, 30), "work": time(7, 30), "university": time(7, 30), "airport": time(18, 0)}


def next_workday_at(t: time, now: datetime) -> datetime:
    local = now.astimezone(RIYADH)
    for add in range(0, 8):
        day = (local + timedelta(days=add)).date()
        cand = datetime.combine(day, t, tzinfo=RIYADH)
        if day.weekday() in WORKDAYS and cand > local + timedelta(minutes=10):
            return cand.astimezone(UTC)
    raise AssertionError("unreachable")


def origin_key(lat: float, lng: float) -> str:
    return f"{lat:.3f},{lng:.3f}"


def compute_commutes(s: Session, google, listing: Listing, now: datetime | None = None) -> dict[str, int | None]:
    if listing.lat is None or listing.lng is None:
        return {}
    now = now or datetime.now(UTC)
    key = origin_key(listing.lat, listing.lng)
    places = list(s.scalars(select(Place).where(Place.kind != "home")))  # home is a trip origin only
    cached = {c.place_id: c.minutes for c in s.scalars(select(CommuteCache).where(CommuteCache.origin_key == key))}
    result = {p.kind: cached[p.id] for p in places if p.id in cached}
    missing = [p for p in places if p.id not in cached]
    by_dep: dict[time, list[Place]] = {}
    for p in missing:
        by_dep.setdefault(DEPARTURE.get(p.kind, time(7, 30)), []).append(p)
    origin = (round(listing.lat, 3), round(listing.lng, 3))
    for dep, group in by_dep.items():
        mins = google.drive_minutes(origin, [(p.lat, p.lng) for p in group], next_workday_at(dep, now))
        for p, m in zip(group, mins):
            s.merge(CommuteCache(origin_key=key, place_id=p.id, minutes=m))
            result[p.kind] = m
    return result
