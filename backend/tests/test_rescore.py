from homefinder import prefs
from homefinder.db import session_scope
from homefinder.models import Listing, PreferenceChange
from homefinder.rescore import apply_score, record_change, rescore_all
from homefinder.schemas import CanonicalFields, RawListing
from homefinder.worker.handlers import WorkerDeps, dispatch
from homefinder.worker.ingest import ingest_raw


def test_apply_score_sets_fields(db):
    p = prefs.get_or_create(db); p.hard_filters = {**p.hard_filters, "price_max": 2_000_000, "min_bedrooms": 6}
    l = Listing(price=1_000_000, bedrooms=5); db.add(l); db.flush()
    apply_score(l, p)
    assert l.passes_filters is False and l.filter_reasons == ["bedrooms_below_min"]
    assert l.score is not None and l.score_breakdown["total"] == l.score


def test_rescore_all_skips_merged(db):
    a = Listing(price=1_000_000); db.add(a); db.flush()
    db.add(Listing(price=1_000_000, merged_into_id=a.id)); db.commit()
    assert rescore_all(db) == 1


def test_ingest_scores_new_listing(db):
    r = ingest_raw(db, RawListing(source="aqar", source_id="1", url="u", fields=CanonicalFields(price=1_000_000, bedrooms=5)))
    assert db.get(Listing, r.listing_id).score_breakdown is not None


def test_record_change_diff(db):
    before = {"hard_filters": {"price_max": 1}, "weights": {"price": 1.0}, "targets": {}}
    after = {"hard_filters": {"price_max": 2}, "weights": {"price": 1.0}, "targets": {}}
    c = record_change(db, "user", before, after, "تعديل الميزانية")
    assert c.diff == {"hard_filters.price_max": {"from": 1, "to": 2}}
    assert record_change(db, "user", after, after, "x") is None
    assert db.query(PreferenceChange).count() == 1


def test_rescore_job(db):
    db.add(Listing(price=1_000_000)); db.commit()
    deps = WorkerDeps(session_factory=session_scope, adapters={}, llm=None, google=None, photo_sink=None, http=None)
    assert dispatch(deps, "rescore_all", {}) == {"rescored": 1}
