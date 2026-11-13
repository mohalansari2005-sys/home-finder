from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from geoalchemy2.elements import WKTElement

from homefinder.models import Listing, Place, VisitStop
from homefinder.server.visits.planner import TripError, departure_utc, plan_trip, replan

RIYADH = ZoneInfo("Asia/Riyadh")


class G:
    def __init__(self, result="ok"): self.result, self.calls = result, []
    def optimize_route(self, origin, stops, dep):
        self.calls.append((origin, stops, dep))
        if self.result is None:
            return None
        n = len(stops)
        return {"order": list(reversed(range(n))), "leg_minutes": [10] * (n + 1)}


def setup(db, n=3):
    db.add(Place(kind="home", name="البيت", lat=24.7, lng=46.6, geom=WKTElement("POINT(46.6 24.7)", srid=4326)))
    ids = []
    for i in range(n):
        l = Listing(title=f"ف{i}", lat=24.8 + i / 100, lng=46.6, family_status="bookmarked"); db.add(l); db.flush(); ids.append(l.id)
    db.commit()
    return ids


NOW = datetime(2026, 11, 13, 9, 0, tzinfo=UTC)


def local(dt):
    return dt.astimezone(RIYADH).strftime("%H:%M")


def test_departure_never_in_past():
    assert departure_utc(date(2026, 11, 1), time(16, 0), NOW) == datetime(2026, 11, 13, 9, 15, tzinfo=UTC)
    assert departure_utc(date(2026, 11, 21), time(16, 0), NOW) == datetime(2026, 11, 21, 13, 0, tzinfo=UTC)
    assert departure_utc(date(2026, 11, 13), time(12, 10), NOW) == datetime(2026, 11, 13, 9, 15, tzinfo=UTC)  # 15 min rule


def test_past_trip_routes_from_now_but_timeline_starts_at_chosen_time(db):
    ids = setup(db, 2)
    g = G()
    trip = plan_trip(db, g, listing_ids=ids, d=date(2026, 11, 1), t=time(16, 0), origin_kind="home",
                     minutes_per_visit=30, now=NOW)
    assert g.calls[0][2] == datetime(2026, 11, 13, 9, 15, tzinfo=UTC)
    assert local(sorted(trip.stops, key=lambda s: s.position)[0].eta) == "16:10"


def test_plan_orders_and_times(db):
    ids = setup(db)
    trip = plan_trip(db, G(), listing_ids=ids, d=date(2026, 11, 21), t=time(16, 0), origin_kind="home",
                     minutes_per_visit=30, now=NOW)
    stops = sorted(trip.stops, key=lambda s: s.position)
    assert [s.listing_id for s in stops] == list(reversed(ids))
    assert [local(s.eta) for s in stops] == ["16:10", "16:50", "17:30"]
    assert [local(s.etd) for s in stops] == ["16:40", "17:20", "18:00"]
    assert [s.drive_min for s in stops] == [10, 10, 10]
    assert trip.total_drive_min == 40
    assert trip.warnings == [] and (trip.origin_lat, trip.origin_lng) == (24.7, 46.6)
    assert trip.status == "planned" and trip.title


def test_plan_with_missing_route(db):
    ids = setup(db, 2)
    trip = plan_trip(db, G(result=None), listing_ids=ids, d=date(2026, 11, 21), t=time(16, 0), origin_kind="home",
                     minutes_per_visit=30, now=NOW)
    assert "no_route" in trip.warnings and all(s.eta is None for s in trip.stops)
    assert [s.listing_id for s in sorted(trip.stops, key=lambda s: s.position)] == ids


def test_plan_without_google_or_when_google_raises(db):
    ids = setup(db, 2)

    class Boom:
        def optimize_route(self, *a): raise RuntimeError("cap")
    for g in (None, Boom()):
        trip = plan_trip(db, g, listing_ids=ids, d=date(2026, 11, 21), t=time(16, 0), origin_kind="home",
                         minutes_per_visit=30, now=NOW)
        assert trip.warnings == ["no_route"] and all(s.eta is None and s.drive_min is None for s in trip.stops)
        assert [s.listing_id for s in sorted(trip.stops, key=lambda s: s.position)] == ids


def test_unreachable_leg_leaves_later_etas_null(db):
    ids = setup(db, 3)

    class Partial:
        def optimize_route(self, o, stops, dep):
            return {"order": [0, 1, 2], "leg_minutes": [10, None, 10, 10]}
    trip = plan_trip(db, Partial(), listing_ids=ids, d=date(2026, 11, 21), t=time(16, 0), origin_kind="home",
                     minutes_per_visit=30, now=NOW)
    stops = sorted(trip.stops, key=lambda s: s.position)
    assert [local(s.eta) if s.eta else None for s in stops] == ["16:10", None, None]
    assert "no_route" in trip.warnings and trip.total_drive_min == 30


def test_listings_without_coords_are_skipped_and_counted(db):
    ids = setup(db, 2)
    nl = Listing(title="x", family_status="bookmarked"); db.add(nl); db.commit()
    trip = plan_trip(db, G(), listing_ids=[*ids, nl.id, ids[0]], d=date(2026, 11, 21), t=time(16, 0),
                     origin_kind="home", minutes_per_visit=30, now=NOW)
    assert len(trip.stops) == 2 and trip.skipped_no_location == 1 and "skipped_no_location" in trip.warnings
    with pytest.raises(TripError):
        plan_trip(db, G(), listing_ids=[nl.id], d=date(2026, 11, 21), t=time(16, 0), origin_kind="home",
                  minutes_per_visit=30, now=NOW)


def test_origin_place_must_be_set(db):
    ids = setup(db, 1)
    for kind, label in [("work", "العمل"), ("school", "المدرسة"), ("university", "الجامعة")]:
        with pytest.raises(TripError, match=f"حدد موقع {label} في الإعدادات أولاً"):
            plan_trip(db, G(), listing_ids=ids, d=date(2026, 11, 21), t=time(16, 0), origin_kind=kind,
                      minutes_per_visit=30, now=NOW)
    db.query(Place).delete(); db.commit()
    with pytest.raises(TripError) as e:
        plan_trip(db, G(), listing_ids=ids, d=date(2026, 11, 21), t=time(16, 0), origin_kind="home",
                  minutes_per_visit=30, now=NOW)
    assert str(e.value) == "حدد موقع المنزل في الإعدادات أولاً"


def test_replan_single_stop(db):
    ids = setup(db, 3)
    g = G()
    trip = plan_trip(db, g, listing_ids=ids, d=date(2026, 11, 21), t=time(16, 0), origin_kind="home", minutes_per_visit=30, now=NOW)
    for s in trip.stops[:2]:
        s.contact_status = "cancelled"
    db.flush()
    replan(db, g, trip)
    assert len(g.calls[-1][1]) == 1
    active = [s for s in trip.stops if s.contact_status != "cancelled"]
    assert len(active) == 1 and active[0].position == 0
    cancelled = [s for s in trip.stops if s.contact_status == "cancelled"]
    assert all(s.eta is None and s.position > 0 for s in cancelled)
    assert trip.total_drive_min == 20


def test_replan_keeps_visited_first_and_clears_no_route(db):
    ids = setup(db, 3)
    g = G()
    trip = plan_trip(db, g, listing_ids=ids, d=date(2026, 11, 21), t=time(16, 0), origin_kind="home", minutes_per_visit=30, now=NOW)
    first = sorted(trip.stops, key=lambda s: s.position)[0]
    first.contact_status = "visited"
    first_eta = first.eta
    trip.warnings = ["no_route", "precheck_pending"]
    db.flush()
    replan(db, g, trip, now=NOW)
    ordered = sorted(trip.stops, key=lambda s: s.position)
    assert ordered[0].id == first.id and ordered[0].eta == first_eta and len(g.calls[-1][1]) == 2
    assert [s.position for s in ordered] == [0, 1, 2]
    assert trip.warnings == ["precheck_pending"]
    assert local(ordered[1].eta) == "16:50"  # the remaining stops start after the visited one ends (16:40) + a 10 min leg
