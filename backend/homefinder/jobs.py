from datetime import timedelta

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from homefinder.models import Job

MAX_ATTEMPTS = 3
BACKOFF = [timedelta(minutes=1), timedelta(minutes=10), timedelta(hours=1)]
STALE_AFTER = timedelta(minutes=15)


def enqueue(s: Session, type: str, payload: dict | None = None, *, dedupe_key: str | None = None,
            priority: int = 0, delay: timedelta | None = None) -> int | None:
    values = dict(type=type, payload=payload or {}, dedupe_key=dedupe_key, priority=priority)
    if delay:
        values["run_after"] = func.now() + delay
    stmt = pg_insert(Job).values(**values)
    if dedupe_key:
        stmt = stmt.on_conflict_do_nothing(index_elements=["dedupe_key"],
                                           index_where=text("status IN ('pending','claimed')"))
    return s.execute(stmt.returning(Job.id)).scalar_one_or_none()


def reclaim_stale(s: Session) -> int:
    cutoff = func.now() - STALE_AFTER
    failed = s.execute(update(Job).where(Job.status == "claimed", Job.claimed_at < cutoff, Job.attempts >= MAX_ATTEMPTS)
                       .values(status="failed", finished_at=func.now(), error="stale: worker never finished")).rowcount
    back = s.execute(update(Job).where(Job.status == "claimed", Job.claimed_at < cutoff)
                     .values(status="pending", claimed_at=None)).rowcount
    return failed + back


def claim(s: Session, types: list[str], n: int = 1) -> list[Job]:
    reclaim_stale(s)
    rows = list(s.scalars(
        select(Job).where(Job.status == "pending", Job.type.in_(types), Job.run_after <= func.now())
        .order_by(Job.priority.desc(), Job.id).limit(n).with_for_update(skip_locked=True)))
    for j in rows:
        j.status = "claimed"
        j.claimed_at = func.now()
        j.attempts += 1
    s.flush()
    for j in rows:
        s.refresh(j)
    return rows


def complete(s: Session, job_id: int, result: dict | None = None) -> bool:
    n = s.execute(update(Job).where(Job.id == job_id, Job.status.in_(["claimed", "pending"]))
                  .values(status="done", finished_at=func.now(), result=result, error=None)).rowcount
    return n == 1


def fail(s: Session, job_id: int, error: str) -> str:
    j = s.get(Job, job_id, with_for_update=True)
    if j is None or j.status == "done":
        return j.status if j else "missing"
    j.error = error[:4000]
    j.claimed_at = None
    if j.attempts >= MAX_ATTEMPTS:
        j.status = "failed"
        j.finished_at = func.now()
    else:
        j.status = "pending"
        j.run_after = func.now() + BACKOFF[max(j.attempts - 1, 0)]
    s.flush()
    return j.status
