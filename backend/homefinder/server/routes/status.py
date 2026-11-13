from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homefinder.models import AdapterHealth, Job, WorkerStatus
from homefinder.server.deps import get_db, require_family

router = APIRouter(dependencies=[Depends(require_family)])
ONLINE_WITHIN = timedelta(minutes=3)


def _iso(d):
    return d.isoformat() if d else None


@router.get("/status")
def status(s: Session = Depends(get_db)):
    w = s.get(WorkerStatus, 1)
    counts = dict(s.execute(select(Job.status, func.count()).group_by(Job.status)).all())
    failed = s.scalars(select(Job).where(Job.status == "failed").order_by(Job.finished_at.desc().nulls_last()).limit(10))
    return {
        "worker": {"online": bool(w and w.last_seen and datetime.now(UTC) - w.last_seen < ONLINE_WITHIN),
                   "last_seen": _iso(w.last_seen) if w else None, "hostname": w.hostname if w else None,
                   "current_job_id": w.current_job_id if w else None},
        "jobs": {k: counts.get(k, 0) for k in ("pending", "claimed", "failed")},
        "adapters": [{"source": a.source, "status": a.status, "reason": a.reason, "last_success_at": _iso(a.last_success_at)}
                     for a in s.scalars(select(AdapterHealth))],
        "failed_jobs": [{"id": j.id, "type": j.type, "error": j.error, "finished_at": _iso(j.finished_at)} for j in failed],
    }
