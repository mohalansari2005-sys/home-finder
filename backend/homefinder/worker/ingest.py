from dataclasses import dataclass

from geoalchemy2.elements import WKTElement
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from homefinder import jobs, prefs
from homefinder.models import Listing, ListingSource, PriceHistory
from homefinder.rescore import apply_score
from homefinder.schemas import RawListing

LISTING_FIELDS = [f for f in RawListing.model_fields["fields"].annotation.model_fields if f not in ("lat", "lng")]


@dataclass
class IngestResult:
    listing_id: int
    created: bool
    price_changed: bool


def set_location(listing: Listing, lat: float | None, lng: float | None, precision: str) -> None:
    if lat is None or lng is None:
        listing.lat = listing.lng = listing.geom = None
        listing.geo_precision = "none"
        return
    listing.lat, listing.lng = lat, lng
    listing.geom = WKTElement(f"POINT({lng} {lat})", srid=4326)
    listing.geo_precision = precision


def _canonical(s: Session, listing: Listing) -> Listing:
    seen = set()
    while listing.merged_into_id and listing.id not in seen:
        seen.add(listing.id)
        listing = s.get(Listing, listing.merged_into_id)
    return listing


def ingest_raw(s: Session, raw: RawListing) -> IngestResult:
    f = raw.fields
    src = s.scalar(select(ListingSource).where(ListingSource.source == raw.source,
                                               ListingSource.source_id == raw.source_id))
    if src is None:
        listing = Listing(**{k: getattr(f, k) for k in LISTING_FIELDS})
        set_location(listing, f.lat, f.lng, raw.geo_precision or "none")
        s.add(listing)
        s.flush()
        s.add(ListingSource(listing_id=listing.id, source=raw.source, source_id=raw.source_id, url=raw.url,
                            raw=raw.raw, photo_urls=raw.photo_urls, seller_phone=raw.seller_phone,
                            seller_name=raw.seller_name, listed_at=raw.listed_at))
        if f.price:
            s.add(PriceHistory(listing_id=listing.id, price=f.price))
        jobs.enqueue(s, "enrich_listing", {"listing_id": listing.id}, dedupe_key=f"enrich:{listing.id}")
        apply_score(listing, prefs.get_or_create(s))
        s.flush()
        return IngestResult(listing.id, created=True, price_changed=False)

    listing = _canonical(s, s.get(Listing, src.listing_id))
    src.raw, src.url, src.fetched_at = raw.raw, raw.url, func.now()
    if raw.photo_urls:
        src.photo_urls = raw.photo_urls
    src.seller_phone = raw.seller_phone or src.seller_phone
    src.seller_name = raw.seller_name or src.seller_name
    # After a merge several sources feed one listing; only the primary (oldest) source drives price and its history,
    # otherwise two sources quoting slightly different prices would flap it and fake price drops.
    primary = s.scalar(select(func.min(ListingSource.id)).where(ListingSource.listing_id == listing.id)) == src.id
    follow_price = primary or listing.price is None
    price_changed = bool(follow_price and f.price and listing.price and f.price != listing.price)
    for k in LISTING_FIELDS:
        v = getattr(f, k)
        if k == "price" and not follow_price:
            continue
        if k == "property_type" and listing.property_type == "townhouse":
            continue  # set from the ad text; the source only ever says villa
        if v is not None:
            setattr(listing, k, v)
    if price_changed:
        s.add(PriceHistory(listing_id=listing.id, price=f.price))
    if f.lat is not None and (listing.lat is None or listing.geo_precision in ("district", "none")):
        set_location(listing, f.lat, f.lng, raw.geo_precision or "exact")
        jobs.enqueue(s, "enrich_listing", {"listing_id": listing.id}, dedupe_key=f"enrich:{listing.id}")
    listing.status = "active"
    listing.last_seen = func.now()
    apply_score(listing, prefs.get_or_create(s))
    s.flush()
    return IngestResult(listing.id, created=False, price_changed=price_changed)
