from datetime import timedelta

from sqlalchemy import func, select, update

from homefinder import jobs
from homefinder.models import Job


def test_enqueue_dedupes_while_active(db):
    a = jobs.enqueue(db, "enrich_listing", {"listing_id": 1}, dedupe_key="enrich:1")
    b = jobs.enqueue(db, "enrich_listing", {"listing_id": 1}, dedupe_key="enrich:1")
    db.commit()
    assert a is not None and b is None
    assert db.scalar(select(func.count()).select_from(Job)) == 1


def test_enqueue_allowed_again_after_done(db):
    a = jobs.enqueue(db, "x", dedupe_key="k"); db.commit()
    [j] = jobs.claim(db, ["x"]); jobs.complete(db, j.id); db.commit()
    assert jobs.enqueue(db, "x", dedupe_key="k") is not None


def test_claim_respects_types_priority_and_run_after(db):
    jobs.enqueue(db, "a", priority=0)
    hi = jobs.enqueue(db, "a", priority=5)
    jobs.enqueue(db, "a", priority=9, delay=timedelta(hours=1))
    jobs.enqueue(db, "b", priority=10)
    db.commit()
    [j] = jobs.claim(db, ["a"])
    assert j.id == hi and j.status == "claimed" and j.attempts == 1


def test_fail_backoff_then_failed(db):
    jid = jobs.enqueue(db, "a"); db.commit()
    for expected in ["pending", "pending", "failed"]:
        db.execute(update(Job).where(Job.id == jid).values(run_after=func.now()))
        [j] = jobs.claim(db, ["a"])
        assert jobs.fail(db, j.id, "boom") == expected
        db.commit()
    j = db.get(Job, jid)
    assert j.error == "boom" and j.attempts == 3


def test_failed_job_is_scheduled_in_future(db):
    jid = jobs.enqueue(db, "a"); db.commit()
    jobs.claim(db, ["a"]); jobs.fail(db, jid, "e"); db.commit()
    assert jobs.claim(db, ["a"]) == []


def test_reclaim_stale_then_complete_once(db):
    jid = jobs.enqueue(db, "a", dedupe_key="only"); db.commit()
    jobs.claim(db, ["a"]); db.commit()
    db.execute(update(Job).where(Job.id == jid).values(claimed_at=func.now() - timedelta(minutes=16)))
    db.commit()
    assert jobs.enqueue(db, "a", dedupe_key="only") is None  # still active, no duplicate
    [again] = jobs.claim(db, ["a"])  # claim() reclaims stale first
    assert again.id == jid and again.attempts == 2
    assert jobs.complete(db, jid) is True
    assert jobs.complete(db, jid) is False  # late completion from the sleeping Mac is a no-op
    db.commit()
    assert db.get(Job, jid).status == "done"


def test_stale_job_past_max_attempts_fails(db):
    jid = jobs.enqueue(db, "a"); db.commit()
    db.execute(update(Job).where(Job.id == jid).values(status="claimed", attempts=3, claimed_at=func.now() - timedelta(minutes=20)))
    db.commit()
    assert jobs.reclaim_stale(db) == 1
    assert db.get(Job, jid).status == "failed"
