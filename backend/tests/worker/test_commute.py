from datetime import UTC, datetime, time

from geoalchemy2.elements import WKTElement

from homefinder.models import CommuteCache, Listing, Place
from homefinder.worker.enrich.commute import compute_commutes, next_workday_at, origin_key


def test_next_workday_skips_friday_saturday():
    # Thursday 2026-11-12 10:00 Riyadh -> next workday 07:30 is Sunday 2026-11-15 07:30 Riyadh = 04:30 UTC
    now = datetime(2026, 11, 12, 7, 0, tzinfo=UTC)
    assert next_workday_at(time(7, 30), now) == datetime(2026, 11, 15, 4, 30, tzinfo=UTC)


def test_next_workday_same_day_if_still_ahead():
    now = datetime(2026, 11, 15, 1, 0, tzinfo=UTC)  # Sunday 04:00 Riyadh
    assert next_workday_at(time(7, 30), now) == datetime(2026, 11, 15, 4, 30, tzinfo=UTC)


def test_origin_key_rounds():
    assert origin_key(24.81234, 46.63449) == "24.812,46.634"


class FakeGoogle:
    def __init__(self): self.calls = []
    def drive_minutes(self, origin, dests, departure):
        self.calls.append((origin, dests, departure))
        return [10 + i for i in range(len(dests))]


def _place(db, kind, lat, lng):
    db.add(Place(kind=kind, name=kind, lat=lat, lng=lng, geom=WKTElement(f"POINT({lng} {lat})", srid=4326)))


def test_compute_commutes_groups_by_departure_and_caches(db):
    for k, la in [("school", 24.7), ("work", 24.71), ("university", 24.72), ("airport", 24.95)]:
        _place(db, k, la, 46.7)
    l = Listing(lat=24.8, lng=46.6); db.add(l); db.commit()
    g = FakeGoogle()
    now = datetime(2026, 11, 12, 7, 0, tzinfo=UTC)
    out = compute_commutes(db, g, l, now=now)
    assert out == {"school": 10, "work": 11, "university": 12, "airport": 10}
    assert len(g.calls) == 2  # morning batch of 3 + evening airport
    db.commit()
    assert compute_commutes(db, g, l, now=now) == out and len(g.calls) == 2  # served from cache
    assert db.query(CommuteCache).count() == 4


def test_home_place_gets_no_commute(db):
    _place(db, "work", 24.71, 46.7)
    _place(db, "home", 24.72, 46.71)
    l = Listing(lat=24.8, lng=46.6); db.add(l); db.commit()
    g = FakeGoogle()
    out = compute_commutes(db, g, l, now=datetime(2026, 11, 12, 7, 0, tzinfo=UTC))
    assert out == {"work": 10} and [len(c[1]) for c in g.calls] == [1]
    assert db.query(CommuteCache).count() == 1
