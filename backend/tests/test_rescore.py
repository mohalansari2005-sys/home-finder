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


def test_cli_rescore_recomputes_every_listing(db):
    from homefinder import cli
    from homefinder.models import Listing
    db.add(Listing(title="x", has_yard=True, has_elevator=True, score=100)); db.commit()
    cli.main(["rescore"])
    db.expire_all()
    l = db.query(Listing).one()
    assert l.score is not None and l.score < 60 and l.score_breakdown["coverage"] < 0.2


def test_preference_writers_take_a_row_lock(db):
    """M13: a learner run and a Settings save must not interleave and overwrite each other's weights."""
    from sqlalchemy import event
    from homefinder import prefs
    from homefinder.db import get_engine, session_scope
    from homefinder.server.routes.settings import PrefsPatch, apply_prefs_patch
    prefs.get_or_create(db); db.commit()
    seen: list[str] = []
    grab = lambda conn, cur, st, *a: seen.append(st)  # noqa: E731
    event.listen(get_engine(), "before_cursor_execute", grab)
    try:
        with session_scope() as s:
            apply_prefs_patch(s, PrefsPatch(weights={"yard": 2}), "user", "x")
        with session_scope() as s:
            from homefinder.learner import run_learn
            run_learn(s)
    finally:
        event.remove(get_engine(), "before_cursor_execute", grab)
    locks = [x for x in seen if "FROM preferences" in x and "FOR UPDATE" in x]
    assert len(locks) >= 2
