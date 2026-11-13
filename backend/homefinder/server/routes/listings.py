from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homefinder import jobs, prefs
from homefinder.models import Listing, ListingSource, Photo, PriceHistory, Reaction
from homefinder.server.deps import get_db, require_family
from homefinder.suggestions import REASON_CODES

router = APIRouter(dependencies=[Depends(require_family)])

DETAIL_FIELDS = ["description", "livings", "building_age_years", "street_width_m", "facing", "street_count",
                 "deed_type", "has_maid_room", "has_driver_room", "has_yard", "has_elevator", "geo_precision",
                 "score_breakdown", "status", "passes_filters", "filter_reasons"]


def _photo_urls(s: Session, ids: list[int]) -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    for p in s.scalars(select(Photo).where(Photo.listing_id.in_(ids)).order_by(Photo.listing_id, Photo.position)):
        out.setdefault(p.listing_id, []).append(f"/photos/{p.path}")
    for src in s.scalars(select(ListingSource).where(ListingSource.listing_id.in_(ids))):
        if src.listing_id not in out and src.photo_urls:
            out[src.listing_id] = list(src.photo_urls)
    return out


DROP_WINDOW = timedelta(days=30)


def _price_drops(s: Session, ids: list[int]) -> dict[int, dict]:
    """{listing_id: {"from", "to", "at"}} when the latest price entry is lower than the previous one and <= 30 days old."""
    if not ids:
        return {}
    rows = s.execute(select(PriceHistory.listing_id, PriceHistory.price, PriceHistory.observed_at)
                     .where(PriceHistory.listing_id.in_(ids))
                     .order_by(PriceHistory.listing_id, PriceHistory.observed_at.desc(), PriceHistory.id.desc())).all()
    latest_two: dict[int, list] = {}
    for lid, price, at in rows:
        if len(latest_two.setdefault(lid, [])) < 2:
            latest_two[lid].append((price, at))
    cutoff = s.scalar(select(func.now())) - DROP_WINDOW
    return {lid: {"from": prev[0], "to": last[0], "at": last[1].isoformat()}
            for lid, (last, prev) in ((k, v) for k, v in latest_two.items() if len(v) == 2)
            if last[0] < prev[0] and last[1] >= cutoff}


def card(l: Listing, photos: list[str] | None, drop: dict | None = None) -> dict:
    return {"id": l.id, "title": l.title, "property_type": l.property_type, "price": l.price, "district": l.district,
            "bedrooms": l.bedrooms, "bathrooms": l.bathrooms, "built_area_m2": l.built_area_m2,
            "land_area_m2": l.land_area_m2, "photo_url": (photos or [None])[0], "score": l.score,
            "commutes": l.commutes or {}, "family_status": l.family_status,
            "status": l.status, "first_seen": l.first_seen.isoformat() if l.first_seen else None, "lat": l.lat, "lng": l.lng,
            "price_drop": drop}


def visible():
    return [Listing.merged_into_id.is_(None)]


@router.get("/feed")
def feed(view: Literal["all", "new", "bookmarked"] = "all", district: str | None = None,
         offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100), s: Session = Depends(get_db)):
    q = select(Listing).where(*visible())
    if view == "bookmarked":
        q = q.where(Listing.family_status.in_(["bookmarked", "visited"]))
    else:
        q = q.where(Listing.status == "active", Listing.passes_filters.is_(True),
                    Listing.family_status.notin_(["rejected"]))
        if view == "new":
            q = q.where(Listing.family_status == "new")
    if district:
        q = q.where(Listing.district == district)
    q = q.order_by(Listing.score.desc().nulls_last(), Listing.first_seen.desc(), Listing.id.desc())
    rows = list(s.scalars(q.offset(offset).limit(limit + 1)))
    more = len(rows) > limit
    rows = rows[:limit]
    ids = [l.id for l in rows]
    photos, drops = _photo_urls(s, ids), _price_drops(s, ids)
    return {"items": [card(l, photos.get(l.id), drops.get(l.id)) for l in rows],
            "next_offset": offset + limit if more else None}


def _detail(s: Session, l: Listing, photos: list[str], drop: dict | None) -> dict:
    out = card(l, photos, drop) | {k: getattr(l, k) for k in DETAIL_FIELDS}
    out["photos"] = photos
    out["sources"] = [{"source": x.source, "url": x.url, "seller_phone": x.seller_phone, "seller_name": x.seller_name}
                      for x in s.scalars(select(ListingSource).where(ListingSource.listing_id == l.id))]
    out["price_history"] = [{"price": p.price, "observed_at": p.observed_at.isoformat()}
                            for p in s.scalars(select(PriceHistory).where(PriceHistory.listing_id == l.id)
                                               .order_by(PriceHistory.observed_at))]
    return out


@router.get("/listings/{listing_id}")
def detail(listing_id: int, s: Session = Depends(get_db)):
    l = s.get(Listing, listing_id)
    if l is None:
        raise HTTPException(404)
    if l.family_status == "new":
        l.family_status = "seen"
    photos = _photo_urls(s, [l.id]).get(l.id, [])
    return _detail(s, l, photos, _price_drops(s, [l.id]).get(l.id))


@router.get("/compare")
def compare(ids: str = Query(...), s: Session = Depends(get_db)):
    """2-4 listings in the requested order, as GET /listings/{id}. Unknown or merged ids are skipped; does not mark anything seen."""
    try:
        wanted = list(dict.fromkeys(int(x) for x in ids.split(",") if x.strip()))
    except ValueError:
        raise HTTPException(422, "ids must be comma-separated integers") from None
    by_id = {l.id: l for l in s.scalars(select(Listing).where(Listing.id.in_(wanted), *visible()))}
    rows = [by_id[i] for i in wanted if i in by_id]
    if not 2 <= len(rows) <= 4:
        raise HTTPException(422, "compare needs 2 to 4 valid listings")
    found = [l.id for l in rows]
    photos, drops = _photo_urls(s, found), _price_drops(s, found)
    return [_detail(s, l, photos.get(l.id, []), drops.get(l.id)) for l in rows]


class ReactBody(BaseModel):
    kind: Literal["bookmark", "reject", "unreject"]
    reason_code: str | None = None
    note: str | None = Field(None, max_length=500)

    @field_validator("reason_code")
    @classmethod
    def _known_reason(cls, v: str | None) -> str | None:
        if v is not None and v not in REASON_CODES:
            raise ValueError(f"reason_code must be one of {REASON_CODES}")
        return v


LEARN_KINDS = ["bookmark", "reject", "visit_rating"]
LEARN_EVERY = 10
NEXT_STATUS = {"bookmark": "bookmarked", "reject": "rejected", "unreject": "seen"}


@router.post("/listings/{listing_id}/react")
def react(listing_id: int, body: ReactBody, s: Session = Depends(get_db)):
    l = s.get(Listing, listing_id)
    if l is None:
        raise HTTPException(404)
    l.family_status = NEXT_STATUS[body.kind]
    reject = body.kind == "reject"  # a reason and note only mean something on a reject
    s.add(Reaction(listing_id=l.id, kind=body.kind, reason_code=body.reason_code if reject else None,
                   note=body.note if reject else None))
    s.flush()
    since = prefs.get_or_create(s).learned_through_reaction_id
    fresh = s.scalar(select(func.count()).select_from(Reaction).where(
        Reaction.id > since, Reaction.kind.in_(LEARN_KINDS)))
    if fresh >= LEARN_EVERY:
        jobs.enqueue(s, "learn", {}, dedupe_key="learn")
    return {"family_status": l.family_status}


@router.get("/map")
def map_points(s: Session = Depends(get_db)):
    rows = list(s.scalars(select(Listing).where(*visible(), Listing.status == "active", Listing.lat.is_not(None),
                                                Listing.family_status != "rejected").limit(2000)))
    photos, drops = _photo_urls(s, [l.id for l in rows]), _price_drops(s, [l.id for l in rows])
    return [{"id": l.id, "lat": l.lat, "lng": l.lng, "price": l.price, "score": l.score,
             "family_status": l.family_status, "status": l.status, "title": l.title,
             "district": l.district, "photo_url": (photos.get(l.id) or [None])[0],
             "price_drop": drops.get(l.id)} for l in rows]
