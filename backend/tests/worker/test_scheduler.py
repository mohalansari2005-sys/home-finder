from datetime import timedelta

from sqlalchemy import func, update

from homefinder import adapters_state
from homefinder.models import Job
from homefinder.worker.scheduler import maybe_schedule


def test_schedules_once_per_interval(db):
    assert maybe_schedule(db, 4) == 1; db.commit()
    j = db.query(Job).one()
    assert j.type == "scrape_search" and j.payload["source"] == "aqar" and j.payload["scheduled"] is True
    assert j.payload["from_prefs"] is True
    assert maybe_schedule(db, 4) == 0  # still active (dedupe) and within interval
    db.execute(update(Job).values(status="done", created_at=func.now() - timedelta(hours=5))); db.commit()
    assert maybe_schedule(db, 4) == 1


def test_skips_paused_adapter(db):
    adapters_state.pause(db, "aqar", "x"); db.commit()
    assert maybe_schedule(db, 4) == 0
