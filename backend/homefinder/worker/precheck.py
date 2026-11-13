import logging

from sqlalchemy import select

from homefinder.models import Listing, VisitStop, VisitTrip
from homefinder.worker.handlers import handle_refresh_listing

log = logging.getLogger(__name__)
TRANSIENT = {"removed", "check_failed"}  # recomputed on every run; price_changed is kept as a record of the change


def _check(deps, listing_id: int) -> dict:
    """Re-fetch one listing through the M3 refresh path (adapter fetch, ingest_raw, price history, paused sources,
    removal only when every source says gone). Never raises: a failed check is a "check_failed" result."""
    try:
        return handle_refresh_listing(deps, {"listing_id": listing_id})
    except Exception as e:  # noqa: BLE001 — one flaky listing must not abort the whole trip check
        log.warning("precheck: listing %s failed: %s", listing_id, e)
        return {"error": str(e)}


def run_precheck(deps, trip_id: int) -> dict:
    with deps.session_factory() as s:
        if s.get(VisitTrip, trip_id) is None:
            return {"skipped": "gone"}
        stops = [(st.id, st.listing_id) for st in s.scalars(
            select(VisitStop).where(VisitStop.trip_id == trip_id, VisitStop.contact_status != "cancelled")
            .order_by(VisitStop.position))]
    removed = changed = 0
    for stop_id, listing_id in stops:
        with deps.session_factory() as s:
            listing = s.get(Listing, listing_id)
            before_price, was_removed = listing.price, listing.status == "removed"
        res = {"removed": True} if was_removed else _check(deps, listing_id)
        new: set[str] = set()
        if res.get("removed"):
            new.add("removed")
        elif res.get("price_changed"):
            new.add("price_changed")
        elif not res.get("refreshed"):
            with deps.session_factory() as s:
                if s.get(Listing, listing_id).status == "removed":  # merged away or removed meanwhile
                    new.add("removed")
                else:
                    new.add("check_failed")
        with deps.session_factory() as s:
            st = s.get(VisitStop, stop_id)
            st.flags = [f for f in (st.flags or []) if f not in TRANSIENT] + sorted(new - set(st.flags or []))
            if "price_changed" in new:
                st.old_price = before_price
        removed += "removed" in new
        changed += "price_changed" in new
    with deps.session_factory() as s:
        trip = s.get(VisitTrip, trip_id)
        trip.warnings = [w for w in (trip.warnings or []) if w != "precheck_pending"]
    return {"checked": len(stops), "removed": removed, "price_changed": changed}
