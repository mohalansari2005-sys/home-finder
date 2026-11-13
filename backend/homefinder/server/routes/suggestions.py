from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder import prefs
from homefinder.models import Listing, Reaction
from homefinder.server.deps import get_db, require_family
from homefinder.server.routes.settings import PrefsPatch, _background_rescore, apply_prefs_patch
from homefinder.suggestions import compute

router = APIRouter(dependencies=[Depends(require_family)])


def _rejects(s: Session) -> list[tuple]:
    rows = s.execute(select(Reaction, Listing).join(Listing, Listing.id == Reaction.listing_id)
                     .where(Reaction.kind == "reject", Listing.family_status == "rejected")  # un-rejected ones don't count
                     .order_by(Reaction.id.desc()).limit(200)).all()
    return [(r.reason_code, l, r.id) for r, l in reversed(rows)]


def current_suggestions(s: Session) -> list[dict]:
    p = prefs.get_or_create(s)
    return compute(_rejects(s), p.hard_filters, (p.targets or {}).get("dismissed_suggestions", []))


def apply_suggestion(s: Session, code: str) -> dict | None:
    """Apply the current suggestion with this code as a user-sourced preference change. None when there is none."""
    sug = next((x for x in current_suggestions(s) if x["code"] == code), None)
    if sug is None:
        return None
    apply_prefs_patch(s, PrefsPatch(**sug["patch"]), "user", sug["text"])
    return sug


@router.get("/suggestions")
def list_suggestions(s: Session = Depends(get_db)):
    return current_suggestions(s)


@router.post("/suggestions/{code}/apply")
def apply(code: str, background: BackgroundTasks, s: Session = Depends(get_db)):
    try:
        sug = apply_suggestion(s, code)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    if sug is None:
        raise HTTPException(404, "no such suggestion")
    s.commit()
    background.add_task(_background_rescore)
    return {"ok": True}


@router.post("/suggestions/{code}/dismiss", status_code=204)
def dismiss(code: str, s: Session = Depends(get_db)):
    if not any(x["code"] == code for x in current_suggestions(s)):
        raise HTTPException(404, "no such suggestion")
    p = prefs.get_or_create(s)
    at = max((rid for _, _, rid in _rejects(s)), default=0)
    targets = dict(p.targets or {})
    targets["dismissed_suggestions"] = [*targets.get("dismissed_suggestions", []), {"code": code, "at_reaction_id": at}]
    p.targets = targets
    return Response(status_code=204)
