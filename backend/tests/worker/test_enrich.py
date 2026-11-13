from contextlib import contextmanager

from homefinder.db import session_scope
from homefinder.models import Listing, ListingSource
from homefinder.usage import BudgetExceeded
from homefinder.worker.enrich.extract import EXTRACTABLE, extract_missing
from homefinder.worker.enrich.pipeline import enrich_listing
from homefinder.worker.handlers import WorkerDeps


class FakeLLM:
    def __init__(self, out=None, exc=None): self.out, self.exc, self.calls = out or {}, exc, []
    def extract_json(self, *, system, user, schema, name):
        self.calls.append(schema)
        if self.exc: raise self.exc
        return {k: self.out.get(k) for k in schema["properties"]}


class FakeMaps:
    def __init__(self): self.calls = 0
    def geocode(self, address): self.calls += 1; return (24.8, 46.6)
    def drive_minutes(self, origin, dests, dep): self.calls += 1; return [15] * len(dests)


def test_extract_only_missing_fields_and_sanity():
    l = Listing(description="فيلا ٥ غرف عمرها ٣٠٠ سنة شارع ٢٠ م", bedrooms=5)
    llm = FakeLLM({"bedrooms": 9, "building_age_years": 300, "street_width_m": 20, "facing": "north"})
    out = extract_missing(llm, l)
    assert "bedrooms" not in llm.calls[0]["properties"]
    assert out == {"street_width_m": 20, "facing": "north"}  # 300-year age rejected by sanity range
    s = llm.calls[0]
    assert s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])


def test_extract_skips_without_text():
    llm = FakeLLM()
    assert extract_missing(llm, Listing(description=None, title=None)) == {} and llm.calls == []


def _deps(llm=None, maps=None):
    return WorkerDeps(session_factory=session_scope, adapters={}, llm=llm, maps=maps, photo_sink=None, http=None)


def test_enrich_without_location(db):
    l = Listing(title="فيلا", description="فيلا للبيع"); db.add(l); db.commit()
    g = FakeMaps()
    out = enrich_listing(_deps(llm=FakeLLM(), maps=g), l.id)
    db.expire_all(); l = db.get(Listing, l.id)
    assert g.calls == 0 and l.geo_precision == "none" and l.commutes == {} and l.enriched_at is not None
    assert out["commutes"] == 0


def test_enrich_geocodes_district_then_commutes(db):
    from tests.worker.test_commute import _place
    _place(db, "work", 24.7, 46.7)
    l = Listing(district="النرجس", city="الرياض"); db.add(l); db.commit()
    g = FakeMaps()
    enrich_listing(_deps(maps=g), l.id)
    db.expire_all(); l = db.get(Listing, l.id)
    assert l.geo_precision == "district" and l.lat == 24.8 and l.commutes == {"work": 15}


def test_enrich_skips_drive_times_for_listings_outside_the_filters(db):
    from homefinder import prefs
    from tests.worker.test_commute import _place
    _place(db, "work", 24.7, 46.7)
    prefs.get_or_create(db).hard_filters = {"price_max": 2_000_000}; db.commit()
    l = Listing(price=5_000_000, lat=24.8, lng=46.6); db.add(l); db.commit()
    g = FakeMaps()
    out = enrich_listing(_deps(maps=g), l.id)
    db.expire_all(); l = db.get(Listing, l.id)
    assert g.calls == 0 and l.commutes == {} and l.passes_filters is False and out["commutes"] == 0


def test_enrich_routes_a_kept_listing_even_outside_the_filters(db):
    from homefinder import prefs
    from tests.worker.test_commute import _place
    _place(db, "work", 24.7, 46.7)
    prefs.get_or_create(db).hard_filters = {"price_max": 2_000_000}; db.commit()
    l = Listing(price=5_000_000, lat=24.8, lng=46.6, family_status="bookmarked"); db.add(l); db.commit()
    enrich_listing(_deps(maps=FakeMaps()), l.id)
    db.expire_all()
    assert db.get(Listing, l.id).commutes == {"work": 15}


def test_enrich_budget_exceeded_keeps_partial_and_requeues(db):
    from homefinder.models import Job
    l = Listing(description="فيلا"); db.add(l); db.commit()
    out = enrich_listing(_deps(llm=FakeLLM(exc=BudgetExceeded("cap"))), l.id)
    assert out["requeued"] is True
    assert db.query(Job).filter(Job.dedupe_key == f"enrich-retry:{l.id}").count() == 1


def test_enrich_merges_duplicates_and_rescores_survivor(db):
    from geoalchemy2.elements import WKTElement
    from homefinder.models import PriceHistory

    def mk(lat, src, sid):
        l = Listing(lat=lat, lng=46.6, geom=WKTElement(f"POINT(46.6 {lat})", srid=4326), geo_precision="exact", price=2_000_000,
                    built_area_m2=400, land_area_m2=300, property_type="villa")
        db.add(l); db.flush()
        db.add(ListingSource(listing_id=l.id, source=src, source_id=sid, url="u", raw={}))
        return l
    old, new = mk(24.8, "aqar", "1"), mk(24.8002, "haraj", "2")
    db.commit()
    out = enrich_listing(_deps(maps=FakeMaps()), new.id)
    db.expire_all()
    assert out["merged_into"] == old.id and db.get(Listing, new.id).merged_into_id == old.id
    assert db.get(Listing, old.id).score is not None


def test_enrich_dedupe_failure_does_not_fail_the_job(db, monkeypatch):
    from homefinder.worker.enrich import pipeline
    monkeypatch.setattr(pipeline, "dedupe_and_merge", lambda s, i: (_ for _ in ()).throw(ValueError("bad phash")))
    l = Listing(title="فيلا", description="x"); db.add(l); db.commit()
    out = enrich_listing(_deps(maps=FakeMaps()), l.id)
    assert "merged_into" not in out


def test_enrich_retry_gives_up_after_five_attempts(db):
    """M12: a permanently failing step (bad key, schema error) must not re-queue itself forever."""
    from homefinder.models import Job
    l = Listing(title="فيلا", description="فيلا للبيع"); db.add(l); db.commit()
    bad = FakeLLM(exc=RuntimeError("bad schema"))
    for attempt in range(0, 5):
        enrich_listing(_deps(llm=bad, maps=FakeMaps()), l.id, attempt=attempt)
        j = db.query(Job).filter_by(type="enrich_listing").one()
        assert j.payload == {"listing_id": l.id, "attempt": attempt + 1}
        db.delete(j); db.commit()
    out = enrich_listing(_deps(llm=bad, maps=FakeMaps()), l.id, attempt=5)
    assert out["requeued"] is False and db.query(Job).filter_by(type="enrich_listing").count() == 0
