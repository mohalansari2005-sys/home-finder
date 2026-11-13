from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder.models import Listing, ListingSource, Photo, PriceHistory, Reaction
from homefinder.server.deps import get_db, require_family

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


def card(l: Listing, photos: list[str] | None) -> dict:
    return {"id": l.id, "title": l.title, "property_type": l.property_type, "price": l.price, "district": l.district,
            "bedrooms": l.bedrooms, "bathrooms": l.bathrooms, "built_area_m2": l.built_area_m2,
            "land_area_m2": l.land_area_m2, "photo_url": (photos or [None])[0], "score": l.score,
            "commutes": l.commutes or {}, "family_status": l.family_status,
            "first_seen": l.first_seen.isoformat() if l.first_seen else None, "lat": l.lat, "lng": l.lng,
            "price_drop": None}


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
    photos = _photo_urls(s, [l.id for l in rows])
    return {"items": [card(l, photos.get(l.id)) for l in rows], "next_offset": offset + limit if more else None}


@router.get("/listings/{listing_id}")
def detail(listing_id: int, s: Session = Depends(get_db)):
    l = s.get(Listing, listing_id)
    if l is None:
        raise HTTPException(404)
    if l.family_status == "new":
        l.family_status = "seen"
    photos = _photo_urls(s, [l.id]).get(l.id, [])
    out = card(l, photos) | {k: getattr(l, k) for k in DETAIL_FIELDS}
    out["photos"] = photos
    out["sources"] = [{"source": x.source, "url": x.url, "seller_phone": x.seller_phone, "seller_name": x.seller_name}
                      for x in s.scalars(select(ListingSource).where(ListingSource.listing_id == l.id))]
    out["price_history"] = [{"price": p.price, "observed_at": p.observed_at.isoformat()}
                            for p in s.scalars(select(PriceHistory).where(PriceHistory.listing_id == l.id)
                                               .order_by(PriceHistory.observed_at))]
    return out


class ReactBody(BaseModel):
    kind: Literal["bookmark", "reject", "unreject"]
    reason_code: str | None = None
    note: str | None = None


NEXT_STATUS = {"bookmark": "bookmarked", "reject": "rejected", "unreject": "seen"}


@router.post("/listings/{listing_id}/react")
def react(listing_id: int, body: ReactBody, s: Session = Depends(get_db)):
    l = s.get(Listing, listing_id)
    if l is None:
        raise HTTPException(404)
    l.family_status = NEXT_STATUS[body.kind]
    s.add(Reaction(listing_id=l.id, kind=body.kind, reason_code=body.reason_code, note=body.note))
    return {"family_status": l.family_status}


@router.get("/map")
def map_points(s: Session = Depends(get_db)):
    rows = list(s.scalars(select(Listing).where(*visible(), Listing.status == "active", Listing.lat.is_not(None),
                                                Listing.family_status != "rejected").limit(2000)))
    photos = _photo_urls(s, [l.id for l in rows])
    return [{"id": l.id, "lat": l.lat, "lng": l.lng, "price": l.price, "score": l.score,
             "family_status": l.family_status, "title": l.title, "district": l.district,
             "photo_url": (photos.get(l.id) or [None])[0]} for l in rows]
