from datetime import date, time

from homefinder import adapters_state
from homefinder.db import session_scope
from homefinder.models import Listing, ListingSource, PriceHistory, VisitStop, VisitTrip
from homefinder.schemas import CanonicalFields, RawListing
from homefinder.worker.handlers import WorkerDeps, dispatch


class A:
    name = "aqar"
    def __init__(self, data): self.data = data; self.fetched = []
    def fetch(self, sid):
        self.fetched.append(sid)
        v = self.data[sid]
        if isinstance(v, Exception):
            raise v
        return v


def mk_trip(db, warnings=None):
    trip = VisitTrip(title="t", date=date(2026, 12, 5), start_time=time(16), origin_kind="home", origin_lat=0, origin_lng=0,
                     minutes_per_visit=30, status="planned", warnings=warnings or [])
    db.add(trip); db.flush()
    return trip


def mk_stop(db, trip, sid, i, price=2_000_000, status="not_contacted", source="aqar"):
    l = Listing(price=price); db.add(l); db.flush()
    db.add(ListingSource(listing_id=l.id, source=source, source_id=sid, url="u", raw={}))
    db.add(VisitStop(trip_id=trip.id, listing_id=l.id, position=i, contact_status=status, flags=[]))
    return l.id


def raw(sid, p):
    return RawListing(source="aqar", source_id=sid, url="u", fields=CanonicalFields(price=p))


def deps_for(adapter):
    return WorkerDeps(session_factory=session_scope, adapters={"aqar": lambda: adapter}, llm=None, google=None,
                      photo_sink=None, http=None)


def test_precheck_flags(db):
    trip = mk_trip(db, warnings=["precheck_pending", "no_route"])
    sids = {sid: mk_stop(db, trip, sid, i) for i, sid in enumerate(["gone", "cheaper", "same", "err"])}
    db.commit()
    adapter = A({"gone": None, "cheaper": raw("cheaper", 1_900_000), "same": raw("same", 2_000_000), "err": RuntimeError("x")})
    out = dispatch(deps_for(adapter), "precheck_trip", {"trip_id": trip.id})
    assert out == {"checked": 4, "removed": 1, "price_changed": 1}
    db.expire_all()
    flags = {s.listing_id: s.flags for s in db.query(VisitStop)}
    assert flags[sids["gone"]] == ["removed"] and flags[sids["cheaper"]] == ["price_changed"]
    assert flags[sids["same"]] == [] and flags[sids["err"]] == ["check_failed"]
    assert db.get(Listing, sids["gone"]).status == "removed" and db.get(Listing, sids["cheaper"]).price == 1_900_000
    assert db.get(VisitTrip, trip.id).warnings == ["no_route"]  # precheck_pending cleared, other warnings kept
    stop = db.query(VisitStop).filter_by(listing_id=sids["cheaper"]).one()
    assert stop.old_price == 2_000_000
    assert [p.price for p in db.query(PriceHistory).filter_by(listing_id=sids["cheaper"])] == [1_900_000]


def test_precheck_skips_cancelled_and_missing_trip(db):
    trip = mk_trip(db)
    mk_stop(db, trip, "a", 0); mk_stop(db, trip, "b", 1, status="cancelled")
    db.commit()
    adapter = A({"a": raw("a", 2_000_000), "b": None})
    assert dispatch(deps_for(adapter), "precheck_trip", {"trip_id": trip.id}) == {"checked": 1, "removed": 0, "price_changed": 0}
    assert adapter.fetched == ["a"]
    assert dispatch(deps_for(adapter), "precheck_trip", {"trip_id": 999}) == {"skipped": "gone"}


def test_rerun_keeps_price_changed_and_clears_stale_failure(db):
    trip = mk_trip(db)
    lid = mk_stop(db, trip, "p", 0)
    db.commit()
    adapter = A({"p": raw("p", 1_800_000)})
    dispatch(deps_for(adapter), "precheck_trip", {"trip_id": trip.id})
    adapter.data["p"] = RuntimeError("blip")
    dispatch(deps_for(adapter), "precheck_trip", {"trip_id": trip.id})
    db.expire_all()
    assert db.query(VisitStop).one().flags == ["price_changed", "check_failed"]
    adapter.data["p"] = raw("p", 1_800_000)  # same price now: the earlier change is still worth showing, the failure is gone
    dispatch(deps_for(adapter), "precheck_trip", {"trip_id": trip.id})
    db.expire_all()
    st = db.query(VisitStop).one()
    assert st.flags == ["price_changed"] and st.old_price == 2_000_000 and db.get(Listing, lid).price == 1_800_000


def test_precheck_reuses_refresh_path_paused_source_is_check_failed_not_removed(db):
    trip = mk_trip(db)
    lid = mk_stop(db, trip, "p", 0)
    db.commit()
    adapters_state.pause(db, "aqar", "app-version outdated"); db.commit()
    adapter = A({"p": None})
    out = dispatch(deps_for(adapter), "precheck_trip", {"trip_id": trip.id})
    assert out == {"checked": 1, "removed": 0, "price_changed": 0} and adapter.fetched == []
    db.expire_all()
    assert db.query(VisitStop).one().flags == ["check_failed"] and db.get(Listing, lid).status == "active"


def test_already_removed_listing_is_flagged_without_fetching(db):
    trip = mk_trip(db)
    lid = mk_stop(db, trip, "r", 0)
    db.get(Listing, lid).status = "removed"; db.commit()
    adapter = A({"r": raw("r", 1)})
    out = dispatch(deps_for(adapter), "precheck_trip", {"trip_id": trip.id})
    assert out == {"checked": 1, "removed": 1, "price_changed": 0} and adapter.fetched == []
    db.expire_all()
    assert db.query(VisitStop).one().flags == ["removed"]
