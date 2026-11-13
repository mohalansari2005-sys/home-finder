from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homefinder import adapters_state, jobs
from homefinder.models import Job

ENABLED_SOURCES: list[str] = ["aqar"]


def maybe_schedule(s: Session, interval_hours: float) -> int:
    n = 0
    for source in ENABLED_SOURCES:
        if adapters_state.is_paused(s, source):
            continue
        last = s.scalar(select(func.max(Job.created_at)).where(
            Job.type == "scrape_search", Job.payload["source"].astext == source,
            Job.payload["scheduled"].astext == "true"))
        if last is not None and s.scalar(select(func.now())) - last < timedelta(hours=interval_hours):
            continue
        if jobs.enqueue(s, "scrape_search", {"source": source, "from_prefs": True, "scheduled": True},
                        dedupe_key=f"scrape:{source}") is not None:
            n += 1
    return n
