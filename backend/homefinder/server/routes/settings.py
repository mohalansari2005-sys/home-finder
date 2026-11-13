from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from geoalchemy2.elements import WKTElement
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from homefinder import jobs, prefs
from homefinder.models import CommuteCache, Place
from homefinder.server.deps import get_db, require_family

router = APIRouter(dependencies=[Depends(require_family)])


class PlaceIn(BaseModel):
    kind: Literal["school", "work", "university", "airport"]
    name: str = Field(min_length=1, max_length=120)
    lat: float = Field(ge=16, le=33)
    lng: float = Field(ge=34, le=56)


def _places(s: Session) -> list[dict]:
    return [{"kind": p.kind, "name": p.name, "lat": p.lat, "lng": p.lng}
            for p in s.scalars(select(Place).order_by(Place.id))]


@router.get("/places")
def get_places(s: Session = Depends(get_db)):
    return _places(s)


@router.put("/places")
def put_places(body: list[PlaceIn], s: Session = Depends(get_db)):
    changed = False
    for p in body:
        row = s.scalar(select(Place).where(Place.kind == p.kind))
        if row is None:
            row = Place(kind=p.kind)
            s.add(row)
        elif (row.lat, row.lng) != (p.lat, p.lng):
            s.flush()
            s.execute(delete(CommuteCache).where(CommuteCache.place_id == row.id))
            changed = True
        else:
            row.name = p.name
            continue
        row.name, row.lat, row.lng = p.name, p.lat, p.lng
        row.geom = WKTElement(f"POINT({p.lng} {p.lat})", srid=4326)
        row.updated_at = func.now()
        changed = True
    if changed:
        jobs.enqueue(s, "recompute_commutes", {}, dedupe_key="recompute_commutes", delay=timedelta(seconds=30))
    s.flush()
    return _places(s)


class PrefsPatch(BaseModel):
    hard_filters: dict | None = None
    weights: dict[str, float] | None = None
    targets: dict | None = None
    locked_weights: list[str] | None = None


def _prefs_out(p) -> dict:
    return {"hard_filters": p.hard_filters, "weights": p.weights, "targets": p.targets, "locked_weights": p.locked_weights}


@router.get("/preferences")
def get_prefs(s: Session = Depends(get_db)):
    return _prefs_out(prefs.get_or_create(s))


@router.put("/preferences")
def put_prefs(body: PrefsPatch, s: Session = Depends(get_db)):
    p = prefs.get_or_create(s)
    if body.hard_filters is not None:
        p.hard_filters = {**p.hard_filters, **body.hard_filters}
    if body.weights is not None:
        p.weights = {**p.weights, **body.weights}
    if body.targets is not None:
        p.targets = {**p.targets, **body.targets}
    if body.locked_weights is not None:
        p.locked_weights = body.locked_weights
    p.updated_at = func.now()
    s.flush()
    return _prefs_out(p)
