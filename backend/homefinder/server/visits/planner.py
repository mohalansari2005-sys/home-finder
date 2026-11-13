import logging
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from homefinder import jobs
from homefinder.models import Job, Listing, Place, VisitStop, VisitTrip
from homefinder.server.visits.links import AR_WEEKDAYS

log = logging.getLogger(__name__)
RIYADH = ZoneInfo("Asia/Riyadh")
MIN_LEAD = timedelta(minutes=15)  # route a departure that has not happened yet
PRECHECK_LEAD = timedelta(hours=3)
ORIGIN_AR = {"home": "المنزل", "school": "المدرسة", "work": "العمل", "university": "الجامعة"}


class TripError(ValueError):
    """A trip request that can't be planned. The message is Arabic and shown to the family as is."""


def _local_start(d: date, t: time) -> datetime:
    return datetime.combine(d, t, tzinfo=RIYADH)


def _departure(start_local: datetime, now: datetime) -> datetime:
    return max(start_local, now + MIN_LEAD).astimezone(UTC)


def departure_utc(d: date, t: time, now: datetime) -> datetime:
    """Routing departure: the chosen local time, but never earlier than now + 15 min."""
    return _departure(_local_start(d, t), now)


def _route(maps, origin, stops: list[Listing], departure: datetime) -> dict | None:
    if maps is None or not stops:
        return None
    try:
        res = maps.optimize_route(origin, [(l.lat, l.lng) for l in stops], departure)
    except Exception as e:  # noqa: BLE001 — quota, outage or a bad stop: keep the requested order instead
        log.warning("route optimization failed: %s", e)
        return None
    if res is None or sorted(res["order"]) != list(range(len(stops))) or len(res["leg_minutes"]) != len(stops) + 1:
        return None
    return res


def _schedule(trip: VisitTrip, stops: list[VisitStop], listings: dict[int, Listing], maps, now: datetime,
              start_local: datetime, first_position: int) -> None:
    """Order `stops` (optimized when TomTom answers), then fill positions, ETAs/ETDs, drive_min and total_drive_min."""
    origin = (trip.origin_lat, trip.origin_lng)
    res = _route(maps, origin, [listings[x.listing_id] for x in stops], _departure(start_local, now))
    warnings = [w for w in (trip.warnings or []) if w != "no_route"]
    if res is None:
        ordered, legs = list(stops), [None] * (len(stops) + 1)
    else:
        ordered, legs = [stops[i] for i in res["order"]], res["leg_minutes"]
    clock: datetime | None = start_local
    total = 0
    for i, st in enumerate(ordered):
        st.position = first_position + i
        leg = legs[i]
        st.drive_min = leg
        if leg is not None:
            total += leg
        if leg is None or clock is None:
            clock = None
            st.eta = st.etd = None
            continue
        eta = clock + timedelta(minutes=leg)
        st.eta, st.etd = eta.astimezone(UTC), (eta + timedelta(minutes=trip.minutes_per_visit)).astimezone(UTC)
        clock = eta + timedelta(minutes=trip.minutes_per_visit)
    if ordered and legs[-1] is not None:
        total += legs[-1]
    if ordered and (res is None or any(x is None for x in legs[:-1])):
        warnings.append("no_route")
    trip.total_drive_min = total if ordered and res is not None else None
    trip.warnings = warnings


def _default_title(rows: list[Listing], d: date) -> str:
    districts = Counter(l.district.strip() for l in rows if l.district and l.district.strip())
    if districts:
        return f"زيارة {districts.most_common(1)[0][0]}"
    return f"زيارة يوم {AR_WEEKDAYS[d.weekday()]}"


def plan_trip(s: Session, maps, *, listing_ids: list[int], d: date, t: time, origin_kind: str,
              minutes_per_visit: int, title: str | None = None, now: datetime | None = None) -> VisitTrip:
    now = now or datetime.now(UTC)
    place = s.scalar(select(Place).where(Place.kind == origin_kind))
    if place is None or place.lat is None or place.lng is None:
        raise TripError(f"حدد موقع {ORIGIN_AR.get(origin_kind, 'نقطة الانطلاق')} في الإعدادات أولاً")
    wanted = list(dict.fromkeys(listing_ids))
    found = {l.id: l for l in s.scalars(select(Listing).where(
        Listing.id.in_(wanted), Listing.merged_into_id.is_(None), Listing.status == "active"))}
    rows = [found[i] for i in wanted if i in found]
    if not rows:
        raise TripError("لا توجد إعلانات صالحة للزيارة")
    located = [l for l in rows if l.lat is not None and l.lng is not None]
    skipped = len(rows) - len(located)
    if not located:
        raise TripError("لا يمكن إضافة هذه الإعلانات لمسار لعدم توفر موقع")
    trip = VisitTrip(title=(title or "").strip() or _default_title(located, d), date=d, start_time=t,
                     origin_kind=origin_kind, origin_lat=place.lat, origin_lng=place.lng,
                     minutes_per_visit=minutes_per_visit, status="planned",
                     warnings=["skipped_no_location"] if skipped else [], skipped_no_location=skipped)
    s.add(trip)
    stops = [VisitStop(trip=trip, listing_id=l.id, position=i, contact_status="not_contacted", flags=[])
             for i, l in enumerate(located)]
    s.add_all(stops)
    s.flush()
    _schedule(trip, stops, {l.id: l for l in located}, maps, now, _local_start(d, t), 0)
    s.flush()
    return trip


def replan(s: Session, maps, trip: VisitTrip, now: datetime | None = None) -> VisitTrip:
    """Re-plan the stops that are neither cancelled nor visited. Visited stops stay first and untouched;
    cancelled ones go last without times. Trip and stop rows are kept."""
    now = now or datetime.now(UTC)
    stops = sorted(trip.stops, key=lambda x: x.position)
    visited = [x for x in stops if x.contact_status == "visited"]
    cancelled = [x for x in stops if x.contact_status == "cancelled"]
    active = [x for x in stops if x.contact_status not in ("visited", "cancelled")]
    for i, st in enumerate(visited):
        st.position = i
    start = _local_start(trip.date, trip.start_time)
    ends = [x.etd.astimezone(RIYADH) for x in visited if x.etd]
    if ends:
        start = max(start, max(ends))  # the remaining visits begin once the last finished one is over
    listings = {l.id: l for l in s.scalars(select(Listing).where(Listing.id.in_([x.listing_id for x in active])))}
    _schedule(trip, active, listings, maps, now, start, len(visited))
    for i, st in enumerate(cancelled):
        st.position = len(visited) + len(active) + i
        st.eta = st.etd = st.drive_min = None
    s.flush()
    return trip


def enqueue_precheck(s: Session, trip_id: int, *, delay: timedelta | None = None, urgent: bool = False) -> None:
    """Queue the pre-trip listing check. An already queued (not yet claimed) check is pulled forward when urgent."""
    key = f"precheck:{trip_id}"
    queued = jobs.enqueue(s, "precheck_trip", {"trip_id": trip_id}, dedupe_key=key,
                          priority=10 if urgent else 0, delay=None if urgent else delay)
    if queued is None and urgent:
        s.execute(update(Job).where(Job.dedupe_key == key, Job.status == "pending")
                  .values(run_after=func.now(), priority=10))


def create_trip_from_request(s: Session, maps, *, listing_ids: list[int], d: date, t: time, origin_kind: str = "home",
                             minutes_per_visit: int = 30, title: str | None = None,
                             now: datetime | None = None) -> VisitTrip:
    """The one code path for creating a trip (HTTP route and agent tool): plan it, then queue the pre-trip check
    3 h before the start (immediately when that moment has passed). Raises TripError."""
    now = now or datetime.now(UTC)
    trip = plan_trip(s, maps, listing_ids=listing_ids, d=d, t=t, origin_kind=origin_kind,
                     minutes_per_visit=minutes_per_visit, title=title, now=now)
    run_at = _local_start(d, t) - PRECHECK_LEAD
    enqueue_precheck(s, trip.id, delay=run_at - now if run_at > now else None)
    trip.warnings = [*trip.warnings, "precheck_pending"]
    s.flush()
    return trip
