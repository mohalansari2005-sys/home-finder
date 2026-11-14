from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from homefinder.models import Listing, ListingSource, VisitPhoto, VisitStop, VisitTrip
from homefinder.server.routes.listings import _photo_urls, _price_drops, card
from homefinder.server.visits.links import google_maps_directions, normalize_sa_mobile, whatsapp_link

RIYADH = ZoneInfo("Asia/Riyadh")
PUBLIC_FLAGS = ("removed", "price_changed")  # check_failed stays internal


def _hhmm(dt: datetime | None) -> str | None:
    return dt.astimezone(RIYADH).strftime("%H:%M") if dt else None


def listing_cards(s: Session, rows: list[Listing]) -> list[dict]:
    ids = [l.id for l in rows]
    photos, drops = _photo_urls(s, ids, first_only=True), _price_drops(s, ids)
    return [card(l, photos.get(l.id), drops.get(l.id)) for l in rows]


def _phones(s: Session, listing_ids: list[int]) -> dict[int, str | None]:
    """First seller phone that is a valid Saudi mobile, per listing (normalized 9665XXXXXXXX)."""
    out: dict[int, str | None] = {}
    for lid, phone in s.execute(select(ListingSource.listing_id, ListingSource.seller_phone)
                                .where(ListingSource.listing_id.in_(listing_ids)).order_by(ListingSource.id)):
        if out.get(lid) is None:
            out[lid] = normalize_sa_mobile(phone)
    return out


def _source_urls(s: Session, listing_ids: list[int]) -> dict[int, str]:
    """URL of each listing's oldest source ad (the one listing detail's `sources` lists first)."""
    out: dict[int, str] = {}
    for lid, url in s.execute(select(ListingSource.listing_id, ListingSource.url)
                              .where(ListingSource.listing_id.in_(listing_ids)).order_by(ListingSource.id)):
        out.setdefault(lid, url)
    return out


def photo_url(photo_id: int) -> str:
    return f"/api/visits/photos/{photo_id}"


def trip_out(s: Session, trip: VisitTrip) -> dict:
    stops = sorted(trip.stops, key=lambda x: x.position)
    ids = [x.listing_id for x in stops]
    listings = {l.id: l for l in s.scalars(select(Listing).where(Listing.id.in_(ids)))} if ids else {}
    cards = {c["id"]: c for c in listing_cards(s, list(listings.values()))}
    phones = _phones(s, ids) if ids else {}
    urls = _source_urls(s, ids) if ids else {}
    photos: dict[int, list[str]] = {}
    if stops:
        for p in s.scalars(select(VisitPhoto).where(VisitPhoto.stop_id.in_([x.id for x in stops])).order_by(VisitPhoto.id)):
            photos.setdefault(p.stop_id, []).append(photo_url(p.id))
    out_stops = []
    for st in stops:
        l = listings[st.listing_id]
        flags = [f for f in PUBLIC_FLAGS if f in (st.flags or [])]
        phone = phones.get(st.listing_id)
        eta_local = st.eta.astimezone(RIYADH).replace(tzinfo=None) if st.eta else None
        out_stops.append({
            "id": st.id, "position": st.position, "listing": cards[st.listing_id],
            "eta_local": _hhmm(st.eta), "etd_local": _hhmm(st.etd), "drive_min": st.drive_min,
            "contact_status": st.contact_status, "rating": st.rating, "notes": st.notes, "flags": flags,
            "old_price": st.old_price if "price_changed" in flags else None,
            "whatsapp_url": whatsapp_link(phone, l.title, eta_local), "phone": phone,
            "source_url": urls.get(st.listing_id), "maps_url": google_maps_directions(l.lat, l.lng),
            "photos": photos.get(st.id, [])})
    return {"id": trip.id, "title": trip.title, "date": trip.date.isoformat(),
            "start_time": trip.start_time.strftime("%H:%M"), "origin_kind": trip.origin_kind,
            "minutes_per_visit": trip.minutes_per_visit, "status": trip.status, "warnings": list(trip.warnings or []),
            "skipped_no_location": trip.skipped_no_location, "total_drive_min": trip.total_drive_min,
            "stops": out_stops}
