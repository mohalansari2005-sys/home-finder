from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from geoalchemy2.elements import WKTElement
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from homefinder import adapters_state, jobs, prefs
from homefinder.db import session_scope
from homefinder.models import CommuteCache, Place, PreferenceChange
from homefinder.prefs_schema import HardFilters, Targets, validate_weights
from homefinder.rescore import record_change, rescore_all, snapshot
from homefinder.scoring import DEFAULT_TARGETS, DEFAULT_WEIGHTS, effective_targets, effective_weights
from homefinder.worker.scheduler import ENABLED_SOURCES
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


SEARCH_KEYS = {"property_types", "districts", "price_max", "city"}


def _prefs_out(p) -> dict:
    return {"hard_filters": p.hard_filters, "weights": effective_weights(p.weights),
            "targets": effective_targets(p.targets), "locked_weights": p.locked_weights,
            "defaults": {"weights": DEFAULT_WEIGHTS, "targets": DEFAULT_TARGETS}}


class PrefsPatch(BaseModel):
    hard_filters: dict | None = None
    weights: dict[str, float] | None = None
    targets: dict | None = None
    unlock: list[str] | None = None
    reset_weights: bool = False


def _background_rescore() -> None:
    with session_scope() as s:
        rescore_all(s)


def _explain(e: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors())


def apply_prefs_patch(s: Session, body: PrefsPatch, source: str, explanation: str) -> dict:
    """Shared by the HTTP route and the chat agent. Raises ValueError on invalid input."""
    p = prefs.get_or_create(s)
    before = snapshot(p)
    try:
        hf = HardFilters(**{**p.hard_filters, **(body.hard_filters or {})}).model_dump()
        tg = Targets(**{**p.targets, **(body.targets or {})}).model_dump(exclude_defaults=True)
        new_w = validate_weights(body.weights or {})
    except ValidationError as e:
        raise ValueError(_explain(e)) from e
    weights = {} if body.reset_weights else {**p.weights, **new_w}
    locked = [] if body.reset_weights else sorted((set(p.locked_weights) | set(new_w)) - set(body.unlock or []))
    p.hard_filters, p.targets, p.weights, p.locked_weights = hf, tg, weights, locked
    p.updated_at = func.now()
    record_change(s, source, before, snapshot(p), explanation)
    if any(before["hard_filters"].get(k) != hf.get(k) for k in SEARCH_KEYS):
        for src in ENABLED_SOURCES:
            jobs.enqueue(s, "scrape_search", {"source": src, "from_prefs": True, "scheduled": False},
                         dedupe_key=f"scrape:{src}", priority=5)
    s.flush()
    return _prefs_out(p)


@router.get("/preferences")
def get_prefs(s: Session = Depends(get_db)):
    return _prefs_out(prefs.get_or_create(s))


@router.put("/preferences")
def put_prefs(body: PrefsPatch, background: BackgroundTasks, s: Session = Depends(get_db)):
    try:
        out = apply_prefs_patch(s, body, "user", "تعديل من صفحة الإعدادات")
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    s.commit()
    background.add_task(_background_rescore)
    return out


@router.get("/preferences/changes")
def changes(limit: int = 20, s: Session = Depends(get_db)):
    rows = s.scalars(select(PreferenceChange).order_by(PreferenceChange.at.desc(), PreferenceChange.id.desc())
                     .limit(max(1, min(limit, 100))))
    return [{"at": c.at.isoformat(), "source": c.source, "diff": c.diff, "explanation": c.explanation} for c in rows]


@router.post("/adapters/{source}/resume", status_code=204)
def resume(source: str, s: Session = Depends(get_db)):
    adapters_state.resume(s, source)
    return Response(status_code=204)
