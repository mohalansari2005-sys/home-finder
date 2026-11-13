from datetime import timedelta

from sqlalchemy import func, update

from homefinder import adapters_state
from homefinder.db import session_scope
from homefinder.models import Job, Listing, ListingSource, PriceHistory
from homefinder.schemas import CanonicalFields, RawListing
from homefinder.worker.handlers import WorkerDeps, dispatch
from homefinder.worker.scheduler import enqueue_stale_refreshes, maybe_schedule


def mk(db, days_ago=4, source="aqar", sid="1", **kw):
    l = Listing(price=2_000_000, last_seen=func.now() - timedelta(days=days_ago), **kw)
    db.add(l); db.flush()
    db.add(ListingSource(listing_id=l.id, source=source, source_id=sid, url=f"https://x/{sid}", raw={}))
    db.add(PriceHistory(listing_id=l.id, price=2_000_000))
    db.commit()
    return l


class FakeAdapter:
    def __init__(self, result=None): self.result, self.fetched = result, []
    def fetch(self, sid): self.fetched.append(sid); return self.result


def deps(**adapters):
    return WorkerDeps(session_factory=session_scope, adapters={k: (lambda a=a: a) for k, a in adapters.items()},
                      llm=None, maps=None, photo_sink=None, http=None)


def raw(price=2_000_000, sid="1", **kw):
    return RawListing(source="aqar", source_id=sid, url="https://x/1", fields=CanonicalFields(price=price, **kw))


def test_stale_listing_enqueued_once_oldest_first_and_fresh_ignored(db):
    old, older, fresh = mk(db, 4, sid="a"), mk(db, 9, sid="b"), mk(db, 1, sid="c")
    assert enqueue_stale_refreshes(db, limit=1) == 1; db.commit()
    j = db.query(Job).filter_by(type="refresh_listing").one()
    assert j.payload == {"listing_id": older.id} and j.dedupe_key == f"refresh:{older.id}"
    assert enqueue_stale_refreshes(db) == 1  # `older` is deduped; only `old` is new
    db.commit()
    ids = {j.payload["listing_id"] for j in db.query(Job).filter_by(type="refresh_listing")}
    assert ids == {old.id, older.id} and fresh.id not in ids


def test_removed_merged_and_inactive_listings_not_refreshed(db):
    keep = mk(db, sid="k")
    mk(db, sid="r", status="removed"); mk(db, sid="m", merged_into_id=keep.id)
    assert enqueue_stale_refreshes(db) == 1


def test_maybe_schedule_also_enqueues_refreshes(db):
    l = mk(db)
    maybe_schedule(db, 4); db.commit()
    assert db.query(Job).filter_by(type="refresh_listing").one().payload == {"listing_id": l.id}
    assert db.query(Job).filter_by(type="scrape_search").count() == 2


def test_gone_listing_is_marked_removed(db):
    l = mk(db)
    maybe_schedule(db, 4); db.commit()
    payload = db.query(Job).filter_by(type="refresh_listing").one().payload
    a = FakeAdapter(None)
    out = dispatch(deps(aqar=a), "refresh_listing", payload)
    db.expire_all()
    assert out == {"removed": True} and a.fetched == ["1"] and db.get(Listing, l.id).status == "removed"


def test_listing_seen_one_day_ago_is_not_enqueued(db):
    mk(db, days_ago=1)
    maybe_schedule(db, 4); db.commit()
    assert db.query(Job).filter_by(type="refresh_listing").count() == 0


def test_refresh_updates_price_and_records_history(db):
    l = mk(db)
    out = dispatch(deps(aqar=FakeAdapter(raw(price=1_900_000))), "refresh_listing", {"listing_id": l.id})
    db.expire_all()
    l = db.get(Listing, l.id)
    assert out["refreshed"] is True and out["price_changed"] is True
    assert l.price == 1_900_000 and l.status == "active"
    assert [p.price for p in db.query(PriceHistory).order_by(PriceHistory.id)] == [2_000_000, 1_900_000]


def test_refresh_keeps_known_fields_when_by_id_response_lacks_them(db):
    l = mk(db, built_area_m2=420.0, bedrooms=5)
    dispatch(deps(aqar=FakeAdapter(raw(price=2_000_000, built_area_m2=None, bedrooms=None))), "refresh_listing", {"listing_id": l.id})
    db.expire_all()
    assert db.get(Listing, l.id).built_area_m2 == 420.0 and db.get(Listing, l.id).bedrooms == 5


def test_refresh_resets_last_seen(db):
    l = mk(db, days_ago=5)
    dispatch(deps(aqar=FakeAdapter(raw())), "refresh_listing", {"listing_id": l.id})
    assert enqueue_stale_refreshes(db) == 0


def test_refresh_paused_adapter_skipped(db):
    l = mk(db)
    adapters_state.pause(db, "aqar", "x"); db.commit()
    a = FakeAdapter(None)
    assert dispatch(deps(aqar=a), "refresh_listing", {"listing_id": l.id}) == {"skipped": "paused"}
    db.expire_all()
    assert a.fetched == [] and db.get(Listing, l.id).status == "active"


def test_removed_only_when_every_source_is_gone(db):
    l = mk(db, sid="a1")
    db.add(ListingSource(listing_id=l.id, source="haraj", source_id="h1", url="https://h/1", raw={})); db.commit()
    gone, alive = FakeAdapter(None), FakeAdapter(raw(sid="h1"))
    out = dispatch(deps(aqar=gone, haraj=alive), "refresh_listing", {"listing_id": l.id})
    db.expire_all()
    assert out["refreshed"] is True and db.get(Listing, l.id).status == "active"
    out = dispatch(deps(aqar=gone, haraj=FakeAdapter(None)), "refresh_listing", {"listing_id": l.id})
    db.expire_all()
    assert out == {"removed": True} and db.get(Listing, l.id).status == "removed"


def test_refresh_missing_or_merged_listing_is_noop(db):
    a = FakeAdapter(None)
    assert dispatch(deps(aqar=a), "refresh_listing", {"listing_id": 12345}) == {"skipped": "gone"}
    k = mk(db, sid="k"); m = mk(db, sid="m", merged_into_id=k.id)
    assert dispatch(deps(aqar=a), "refresh_listing", {"listing_id": m.id}) == {"skipped": "gone"}
    assert a.fetched == []


def test_refresh_outdated_app_version_pauses_adapter(db):
    from homefinder.models import AdapterHealth
    from homefinder.worker.sources.aqar_transport import AppVersionOutdated
    l = mk(db)

    class Out:
        def fetch(self, sid): raise AppVersionOutdated("v")

    out = dispatch(deps(aqar=Out()), "refresh_listing", {"listing_id": l.id})
    assert out == {"skipped": "app_version_outdated"}
    with session_scope() as s:
        assert s.get(AdapterHealth, "aqar").status == "paused"


def test_not_removed_when_the_other_source_is_paused(db):
    l = mk(db, sid="a1")
    db.add(ListingSource(listing_id=l.id, source="haraj", source_id="h1", url="https://h/1", raw={})); db.commit()
    adapters_state.pause(db, "haraj", "x"); db.commit()
    out = dispatch(deps(aqar=FakeAdapter(None), haraj=FakeAdapter(None)), "refresh_listing", {"listing_id": l.id})
    db.expire_all()
    assert out == {"skipped": "paused"} and db.get(Listing, l.id).status == "active"


def test_recompute_commutes_skips_removed_and_rejected_listings(db):
    from homefinder.models import Place
    from geoalchemy2.elements import WKTElement
    db.add(Place(kind="work", name="w", lat=24.7, lng=46.7, geom=WKTElement("POINT(46.7 24.7)", srid=4326))); db.commit()
    live = mk(db, sid="a", lat=24.8, lng=46.6)
    mk(db, sid="b", lat=24.8, lng=46.61, status="removed")
    mk(db, sid="c", lat=24.8, lng=46.62, family_status="rejected")
    mk(db, sid="d", lat=24.8, lng=46.63, family_status="bookmarked")
    asked = []

    class G:
        def drive_minutes(self, origin, dests, dep): asked.append(origin); return [9] * len(dests)

    d = deps(); d.maps = G()
    out = dispatch(d, "recompute_commutes", {})
    assert out == {"listings": 2} and len(asked) == 2  # the live one and the bookmarked one only
