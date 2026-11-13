import hmac
from collections.abc import Iterator

from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session

from homefinder.config import get_settings
from homefinder.db import SessionLocal


def get_db() -> Iterator[Session]:
    s = SessionLocal()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def require_family(request: Request) -> None:
    if not request.session.get("family"):
        raise HTTPException(401, "login required")


def require_worker(authorization: str = Header(default="")) -> None:
    expected = f"Bearer {get_settings().worker_token}"
    if not hmac.compare_digest(authorization.encode(), expected.encode()):
        raise HTTPException(401, "bad worker token")
