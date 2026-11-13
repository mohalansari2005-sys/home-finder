import re
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from homefinder import jobs
from homefinder.config import get_settings
from homefinder.models import Listing, Photo, WorkerStatus
from homefinder.server.deps import get_db, require_worker

router = APIRouter(dependencies=[Depends(require_worker)])


class ClaimBody(BaseModel):
    types: list[str]
    n: int = 1


class CompleteBody(BaseModel):
    result: dict | None = None


class FailBody(BaseModel):
    error: str


class HeartbeatBody(BaseModel):
    hostname: str
    version: str
    current_job_id: int | None = None


@router.post("/claim")
def claim(body: ClaimBody, s: Session = Depends(get_db)):
    return [{"id": j.id, "type": j.type, "payload": j.payload, "attempts": j.attempts}
            for j in jobs.claim(s, body.types, min(body.n, 10))]


@router.post("/complete/{job_id}")
def complete(job_id: int, body: CompleteBody, s: Session = Depends(get_db)):
    return {"ok": jobs.complete(s, job_id, body.result)}


@router.post("/fail/{job_id}")
def fail(job_id: int, body: FailBody, s: Session = Depends(get_db)):
    return {"status": jobs.fail(s, job_id, body.error)}


@router.post("/heartbeat", status_code=204)
def heartbeat(body: HeartbeatBody, s: Session = Depends(get_db)):
    row = s.get(WorkerStatus, 1) or WorkerStatus(id=1)
    row.last_seen, row.hostname, row.version, row.current_job_id = func.now(), body.hostname, body.version, body.current_job_id
    s.add(row)
    return Response(status_code=204)


MAX_UPLOAD = 10 * 1024 * 1024


@router.post("/photos", status_code=204)
def upload_photo(listing_id: int = Form(...), position: int = Form(..., ge=0, le=50), phash: str = Form(""),
                 source_url: str = Form(""), file: UploadFile = File(...), s: Session = Depends(get_db)):
    if phash and not re.fullmatch(r"[0-9a-f]{1,32}", phash):
        raise HTTPException(422, "bad phash")
    if s.get(Listing, listing_id) is None:
        raise HTTPException(404, "listing not found")
    data = file.file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "photo too large")
    rel = f"{listing_id}/{position}.webp"
    dest = Path(get_settings().photos_dir) / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    stmt = pg_insert(Photo).values(listing_id=listing_id, position=position, path=rel, phash=phash or None,
                                   source_url=source_url or None)
    s.execute(stmt.on_conflict_do_update(index_elements=["listing_id", "position"],
                                         set_={"path": rel, "phash": phash or None, "source_url": source_url or None}))
    return Response(status_code=204)
