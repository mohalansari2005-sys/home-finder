import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homefinder.config import get_settings
from homefinder.models import AdapterHealth, Job, Listing, WorkerStatus
from homefinder.server.deps import get_db, require_family

router = APIRouter(dependencies=[Depends(require_family)])
ONLINE_WITHIN = timedelta(minutes=3)


def _iso(d):
    return d.isoformat() if d else None


def _listing_counts(s: Session) -> dict:
    base = (Listing.merged_into_id.is_(None), Listing.status == "active")
    n = lambda *c: s.scalar(select(func.count()).select_from(Listing).where(*base, *c)) or 0  # noqa: E731
    return {"active": n(), "new": n(Listing.family_status == "new"),
            "bookmarked": n(Listing.family_status.in_(["bookmarked", "visited"])),
            "rejected": n(Listing.family_status == "rejected"),
            "passing": n(Listing.passes_filters.is_(True), Listing.family_status != "rejected")}


def _disk() -> dict | None:
    """Free space on the volume that holds the photos (and the nightly dumps): the first thing to fill up."""
    p = Path(get_settings().photos_dir)
    while not p.exists() and p != p.parent:
        p = p.parent
    try:
        u = shutil.disk_usage(p)
    except OSError:
        return None
    return {"free_gb": round(u.free / 2**30, 1), "total_gb": round(u.total / 2**30, 1)}


@router.get("/status")
def status(s: Session = Depends(get_db)):
    w = s.get(WorkerStatus, 1)
    counts = dict(s.execute(select(Job.status, func.count()).group_by(Job.status)).all())
    src = Job.payload["source"].astext
    last_scrape = dict(s.execute(select(src, func.max(Job.finished_at))
                                 .where(Job.type == "scrape_search", Job.status == "done").group_by(src)).all())
    failed = s.scalars(select(Job).where(Job.status == "failed").order_by(Job.finished_at.desc().nulls_last()).limit(10))
    return {
        "worker": {"online": bool(w and w.last_seen and datetime.now(UTC) - w.last_seen < ONLINE_WITHIN),
                   "last_seen": _iso(w.last_seen) if w else None, "hostname": w.hostname if w else None,
                   "current_job_id": w.current_job_id if w else None},
        "jobs": {k: counts.get(k, 0) for k in ("pending", "claimed", "failed")},
        "adapters": [{"source": a.source, "status": a.status, "reason": a.reason, "last_success_at": _iso(a.last_success_at),
                     "last_scrape_at": _iso(last_scrape.get(a.source))}
                     for a in s.scalars(select(AdapterHealth))],
        "counts": _listing_counts(s),
        "disk": _disk(),
        "failed_jobs": [{"id": j.id, "type": j.type, "error": j.error, "finished_at": _iso(j.finished_at)} for j in failed],
    }
