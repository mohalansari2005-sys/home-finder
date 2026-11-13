from datetime import timedelta

from sqlalchemy import func, update

from homefinder import adapters_state
from homefinder.models import Job
from homefinder.worker.scheduler import maybe_schedule


def test_schedules_once_per_interval(db):
    assert maybe_schedule(db, 4) == 2; db.commit()
    js = db.query(Job).order_by(Job.id).all()
    assert [j.payload["source"] for j in js] == ["aqar", "haraj"]
    assert all(j.type == "scrape_search" and j.payload["scheduled"] is True and j.payload["from_prefs"] is True for j in js)
    assert maybe_schedule(db, 4) == 0  # still active (dedupe) and within interval
    db.execute(update(Job).values(status="done", created_at=func.now() - timedelta(hours=5))); db.commit()
    assert maybe_schedule(db, 4) == 2


def test_skips_paused_adapter(db):
    adapters_state.pause(db, "aqar", "x"); db.commit()
    assert maybe_schedule(db, 4) == 1  # haraj still scheduled
    adapters_state.pause(db, "haraj", "x"); db.commit()
    assert maybe_schedule(db, 4) == 0
