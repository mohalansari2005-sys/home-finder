"""Duplicate detection across sources (spec 5.2): within 50 m, areas within 5%, price within 3%, and (when both
have photos) at least one photo pair with perceptual-hash distance <= 8. Runs in the worker (needs imagehash)."""
import imagehash
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from homefinder.models import Listing, ListingSource, Photo, Reaction, VisitStop

RADIUS_M = 50
AREA_TOL, PRICE_TOL, HASH_MAX = 0.05, 0.03, 8
FILLABLE = ["title", "description", "district", "price", "bedrooms", "bathrooms", "livings", "built_area_m2",
            "land_area_m2", "building_age_years", "street_width_m", "facing", "street_count", "deed_type",
            "has_maid_room", "has_driver_room", "has_yard", "has_elevator"]
STATUS_RANK = {"visited": 4, "bookmarked": 3, "rejected": 2, "seen": 1, "new": 0}


def _close(a, b, tol) -> bool | None:
    if a is None or b is None:
        return None
    return abs(a - b) <= tol * max(a, b)


def _hash_match(ha: list[str], hb: list[str]) -> bool:
    hs_a = [imagehash.hex_to_hash(h) for h in ha]
    hs_b = [imagehash.hex_to_hash(h) for h in hb]
    return any(x - y <= HASH_MAX for x in hs_a for y in hs_b)


def is_duplicate(a: Listing, b: Listing, a_hashes: list[str], b_hashes: list[str]) -> bool:
    areas = [r for r in (_close(a.built_area_m2, b.built_area_m2, AREA_TOL),
                         _close(a.land_area_m2, b.land_area_m2, AREA_TOL)) if r is not None]
    if not areas or not all(areas):
        return False
    if not _close(a.price, b.price, PRICE_TOL):
        return False
    if a_hashes and b_hashes:
        return _hash_match(a_hashes, b_hashes)
    return bool(a.property_type and a.property_type == b.property_type)


def _hashes(s: Session, lid: int) -> list[str]:
    return [h for h in s.scalars(select(Photo.phash).where(Photo.listing_id == lid)) if h]


def find_duplicate(s: Session, l: Listing) -> Listing | None:
    if l.geom is None or l.geo_precision not in ("exact", "approximate"):
        return None
    cands = list(s.scalars(select(Listing).where(
        Listing.id != l.id, Listing.merged_into_id.is_(None), Listing.status == "active",
        Listing.geo_precision.in_(["exact", "approximate"]),
        func.ST_DWithin(Listing.geom, l.geom, RADIUS_M)).order_by(Listing.id)))
    mine = _hashes(s, l.id)
    for c in cands:
        if is_duplicate(c, l, _hashes(s, c.id), mine):
            return c
    return None


def merge(s: Session, keep: Listing, dup: Listing) -> None:
    """Fold `dup` into `keep`: fill gaps, keep the stronger family status, move sources and reactions.

    Price history stays with each listing's own row: mixing two sources' prices into one series would show a
    false price drop (aqar 2.0M vs haraj 1.95M for the same house)."""
    for f in FILLABLE:
        if getattr(keep, f) is None and getattr(dup, f) is not None:
            setattr(keep, f, getattr(dup, f))
    if STATUS_RANK.get(dup.family_status, 0) > STATUS_RANK.get(keep.family_status, 0):
        keep.family_status = dup.family_status
    for model in (ListingSource, Reaction, VisitStop):  # trip stops follow the surviving listing
        s.execute(update(model).where(model.listing_id == dup.id).values(listing_id=keep.id))
    if not _hashes(s, keep.id):
        s.execute(update(Photo).where(Photo.listing_id == dup.id).values(listing_id=keep.id))
        keep.photos_fetched = True
    dup.merged_into_id = keep.id
    s.flush()


def dedupe_and_merge(s: Session, listing_id: int) -> int | None:
    l = s.get(Listing, listing_id)
    if l is None or l.merged_into_id:
        return None
    other = find_duplicate(s, l)
    if other is None:
        return None
    keep, dup = (other, l) if other.id < l.id else (l, other)
    merge(s, keep, dup)
    return keep.id
