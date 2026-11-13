import uuid
from datetime import date, time
from functools import lru_cache
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder.config import get_settings
from homefinder.integrations.google import make_google
from homefinder.models import Listing, Reaction, VisitPhoto, VisitStop, VisitTrip
from homefinder.server.deps import get_db, require_family
from homefinder.server.routes.listings import enqueue_learn_if_due
from homefinder.server.visits.grouping import group_bookmarks
from homefinder.server.visits.out import listing_cards, trip_out
from homefinder.server.visits.planner import TripError, create_trip_from_request, enqueue_precheck, replan

router = APIRouter(dependencies=[Depends(require_family)])

MAX_PHOTO_BYTES = 8 * 1024 * 1024
IMAGE_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/heic": "heic",
             "image/heif": "heif", "image/gif": "gif"}  # no svg: it can carry script and is served from our origin
EXT_TYPE = {v: k for k, v in IMAGE_EXT.items()}


@lru_cache
def _http() -> httpx.Client:
    return httpx.Client(timeout=30)


def get_google():
    """The server's Google client (None without a key). Created lazily; tests replace this function."""
    return make_google(_http())


def _trip(s: Session, trip_id: int) -> VisitTrip:
    t = s.get(VisitTrip, trip_id)
    if t is None:
        raise HTTPException(404, "trip not found")
    return t


@router.get("/visits/groups")
def groups(s: Session = Depends(get_db)):
    gs, no_coords = group_bookmarks(s, get_google())
    by_id = {c["id"]: c for c in listing_cards(
        s, list(s.scalars(select(Listing).where(Listing.id.in_([i for g in gs for i in g.listing_ids] + no_coords)))))}
    return {"groups": [{"key": g.key, "districts": g.districts, "listing_ids": g.listing_ids, "count": g.count,
                        "avg_score": g.avg_score, "centroid": list(g.centroid),
                        "listings": [by_id[i] for i in g.listing_ids]} for g in gs],
            "no_location": [by_id[i] for i in no_coords]}


class TripIn(BaseModel):
    listing_ids: list[int] = Field(min_length=1, max_length=15)
    date: date
    start_time: time
    origin_kind: Literal["home", "school", "work", "university"] = "home"
    minutes_per_visit: int = Field(30, ge=15, le=120)
    title: str | None = Field(None, max_length=160)


@router.post("/visits/trips")
def create_trip(body: TripIn, s: Session = Depends(get_db)):
    try:
        trip = create_trip_from_request(s, get_google(), listing_ids=body.listing_ids, d=body.date,
                                        t=body.start_time.replace(second=0, microsecond=0, tzinfo=None),
                                        origin_kind=body.origin_kind, minutes_per_visit=body.minutes_per_visit,
                                        title=body.title)
    except TripError as e:
        raise HTTPException(422, str(e)) from e
    return trip_out(s, trip)


@router.get("/visits/trips")
def list_trips(status: Literal["planned", "done", "all"] = "all", s: Session = Depends(get_db)):
    q = select(VisitTrip)
    if status != "all":
        q = q.where(VisitTrip.status == status)
    trips = s.scalars(q.order_by(VisitTrip.date.desc(), VisitTrip.start_time.desc(), VisitTrip.id.desc()))
    return [trip_out(s, t) for t in trips]


@router.get("/visits/trips/{trip_id}")
def get_trip(trip_id: int, s: Session = Depends(get_db)):
    return trip_out(s, _trip(s, trip_id))


class TripPatch(BaseModel):
    status: Literal["planned", "done", "cancelled"]


@router.patch("/visits/trips/{trip_id}")
def patch_trip(trip_id: int, body: TripPatch, s: Session = Depends(get_db)):
    t = _trip(s, trip_id)
    t.status = body.status
    s.flush()
    return trip_out(s, t)


@router.post("/visits/trips/{trip_id}/replan")
def replan_trip(trip_id: int, s: Session = Depends(get_db)):
    t = _trip(s, trip_id)
    replan(s, get_google(), t)
    return trip_out(s, t)


@router.post("/visits/trips/{trip_id}/precheck", status_code=202)
def precheck(trip_id: int, s: Session = Depends(get_db)):
    t = _trip(s, trip_id)
    enqueue_precheck(s, t.id, urgent=True)
    if "precheck_pending" not in (t.warnings or []):
        t.warnings = [*(t.warnings or []), "precheck_pending"]
    return {"queued": True}


class StopPatch(BaseModel):
    contact_status: Literal["not_contacted", "contacted", "confirmed", "visited", "cancelled"] | None = None
    rating: int | None = Field(None, ge=1, le=5)
    notes: str | None = Field(None, max_length=2000)


@router.patch("/visits/stops/{stop_id}")
def patch_stop(stop_id: int, body: StopPatch, s: Session = Depends(get_db)):
    st = s.get(VisitStop, stop_id)
    if st is None:
        raise HTTPException(404, "stop not found")
    listing = s.get(Listing, st.listing_id)
    needs_replan = False
    if body.contact_status is not None and body.contact_status != st.contact_status:
        before, st.contact_status = st.contact_status, body.contact_status
        needs_replan = body.contact_status == "cancelled"
        if body.contact_status == "visited":
            listing.family_status = "visited"
        elif before == "visited" and listing.family_status == "visited":
            listing.family_status = "bookmarked"  # marked visited by mistake
    if "notes" in body.model_fields_set:
        st.notes = (body.notes or "").strip() or None
    if body.rating is not None and body.rating != st.rating:
        st.rating = body.rating
        s.add(Reaction(listing_id=st.listing_id, kind="visit_rating", rating=body.rating))
        s.flush()
        enqueue_learn_if_due(s)
    s.flush()
    if needs_replan:
        replan(s, get_google(), st.trip)
    return trip_out(s, st.trip)


def _photo_root() -> Path:
    return Path(get_settings().visit_photos_dir)


@router.post("/visits/stops/{stop_id}/photos", status_code=204)
def upload_photo(stop_id: int, file: UploadFile = File(...), s: Session = Depends(get_db)):
    if s.get(VisitStop, stop_id) is None:
        raise HTTPException(404, "stop not found")
    ext = IMAGE_EXT.get((file.content_type or "").lower())
    if ext is None:
        raise HTTPException(422, "الملف يجب أن يكون صورة (JPEG أو PNG أو WebP أو HEIC)")
    data = file.file.read(MAX_PHOTO_BYTES + 1)
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(413, "حجم الصورة أكبر من 8 ميغابايت")
    rel = f"{stop_id}/{uuid.uuid4().hex}.{ext}"
    dest = _photo_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    s.add(VisitPhoto(stop_id=stop_id, path=rel))
    return Response(status_code=204)


@router.get("/visits/photos/{photo_id}")
def get_photo(photo_id: int, s: Session = Depends(get_db)):
    p = s.get(VisitPhoto, photo_id)
    root = _photo_root().resolve()
    path = (root / p.path).resolve() if p else None
    if p is None or not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(404, "photo not found")
    return FileResponse(path, media_type=EXT_TYPE.get(path.suffix[1:], "application/octet-stream"),
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=86400"})
