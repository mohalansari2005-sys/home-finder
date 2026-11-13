from sqlalchemy import func
from sqlalchemy.orm import Session

from homefinder.models import AdapterHealth


def _row(s: Session, source: str) -> AdapterHealth:
    row = s.get(AdapterHealth, source)
    if row is None:
        row = AdapterHealth(source=source, status="ok")
        s.add(row)
    return row


def is_paused(s: Session, source: str) -> bool:
    row = s.get(AdapterHealth, source)
    return bool(row and row.status == "paused")


def pause(s: Session, source: str, reason: str) -> None:
    row = _row(s, source); row.status, row.reason, row.updated_at = "paused", reason, func.now()


def mark_ok(s: Session, source: str) -> None:
    row = _row(s, source); row.status, row.reason, row.updated_at, row.last_success_at = "ok", None, func.now(), func.now()


def resume(s: Session, source: str) -> None:
    row = _row(s, source); row.status, row.reason, row.updated_at = "ok", None, func.now()
